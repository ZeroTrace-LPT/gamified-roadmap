"""Tests for source-preserving Excel import."""

from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from openpyxl import Workbook, load_workbook

from app.database.connection import connect_database
from app.importers.excel_importer import import_excel
from app.gamification.progression import calculate_progression, parse_level_definitions
from app.models.roadmap import ProgressUpdate
from app.services.gamification_service import get_gamification_data, sync_xp_awards
from app.services.quest_service import get_quest_board, get_recommended_quests, set_prerequisites_verified
from app.services.skill_tree_service import get_skill_tree
from app.services.roadmap_service import (
    clear_item_progress,
    get_dashboard_data,
    get_roadmap_item,
    get_roadmap_items,
    save_item_progress,
)


class ExcelImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.root = Path(self.temp_dir.name)
        self.workbook_path = self.root / "source.xlsx"
        self.database_path = self.root / "roadmap.sqlite3"
        self._make_workbook()
        self.connection = connect_database(self.database_path)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp_dir.cleanup()

    def _make_workbook(self) -> None:
        workbook = Workbook()
        dashboard = workbook.active
        dashboard.title = "Dashboard"
        dashboard["B4"] = "Local Test Profile"
        dashboard["E8"] = "=SUM(Roadmap!H2:H63)"
        dashboard["E9"] = 1
        dashboard["C15"] = "IT Apprentice"
        for column, value in enumerate(("Level", "XP Band", "Title", "Unlock", "Reward"), 1):
            dashboard.cell(14, column, value)
        for row, values in enumerate((
            (1, "0-99", "IT Apprentice", "Start", "Build homelab"),
            (2, "100-199", "Network Scout", "100 XP", "Network+"),
            (3, "200+", "Security Practitioner", "200 XP", "Capstone"),
        ), 15):
            for column, value in enumerate(values, 1):
                dashboard.cell(row, column, value)

        roadmap = workbook.create_sheet("Roadmap")
        roadmap.append(["Month", "Age", "Year", "Track", "Focus", "Monthly Mission", "Status", "XP", "Done?", "Notes"])
        roadmap.append(["2026-09", "19", "Year 1", "Foundation", "Network+ / Linux / Git", "Build a lab", "Not Started", 0, "No", "source note"])

        skills = workbook.create_sheet("Skill Matrix")
        skills.append(["Skill", "Track", "Target Age", "What Good Looks Like", "Status", "XP Value"])
        skills.append(["Networking", "Foundation", "20", "TCP/IP", "Not Started", 500])
        certs = workbook.create_sheet("Certifications")
        certs.append(["Certification", "Status", "Domain", "Target Age", "Target Window", "Priority"])
        certs.append(["CompTIA A+", "Completed", "IT Foundations", "19", "Completed", "Done"])
        projects = workbook.create_sheet("Projects")
        projects.append(["ID", "Project", "Track", "Definition of Done", "Target", "XP", "Status"])
        projects.append(["P01", "Homelab v1", "Foundation", "AD + Windows + Linux", "Year 1", 100, "Not Started"])

        starter = workbook.create_sheet("12-Month Starter")
        starter["C5"] = "=IF(B5=0,0,C5/B5)"
        workbook.create_sheet("Microsoft Track")
        wallet = workbook.create_sheet("My Certifications")
        wallet["A25"] = "Cisco CCNA"
        wallet["F25"] = "Planned"
        workbook.create_sheet("Scripting & Dev")
        workbook.create_sheet("Beyond 25")
        workbook.create_sheet("Weekly Tracker")
        workbook.create_sheet("GitHub Portfolio")
        workbook.create_sheet("Resources")
        workbook.create_sheet("Lists")
        workbook.save(self.workbook_path)

    def test_import_persists_source_rows_cells_and_formulas(self) -> None:
        result = import_excel(self.connection, self.workbook_path)

        self.assertEqual(result.sheet_count, 14)
        self.assertGreater(result.source_cell_count, 20)
        self.assertEqual(result.formula_count, 2)
        formula = self.connection.execute(
            "SELECT formula_text FROM source_cells WHERE sheet_name='12-Month Starter' AND coordinate='C5'"
        ).fetchone()[0]
        self.assertEqual(formula, "=IF(B5=0,0,C5/B5)")
        source_note = self.connection.execute(
            "SELECT values_json FROM source_rows WHERE sheet_name='Roadmap' AND row_number=2"
        ).fetchone()[0]
        self.assertIn("source note", source_note)
        self.assertTrue(any(issue.code == "FORMULA_CIRCULAR_REFERENCE" for issue in result.issues))

    def test_normalized_item_keeps_status_and_source_reward(self) -> None:
        import_excel(self.connection, self.workbook_path)
        row = self.connection.execute(
            "SELECT name, status, xp_reward, category, target_period FROM roadmap_items WHERE item_type='monthly_mission'"
        ).fetchone()
        self.assertEqual(tuple(row), ("Network+ / Linux / Git", "Not Started", 100, "Foundation", "2026-09"))

    def test_reimport_of_identical_workbook_is_idempotent(self) -> None:
        first = import_excel(self.connection, self.workbook_path)
        second = import_excel(self.connection, self.workbook_path)
        self.assertFalse(first.already_imported)
        self.assertTrue(second.already_imported)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM workbooks").fetchone()[0], 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM roadmap_items").fetchone()[0], 5)

    def test_changed_workbook_creates_a_distinct_snapshot(self) -> None:
        first = import_excel(self.connection, self.workbook_path)
        workbook = load_workbook(self.workbook_path)
        workbook["Roadmap"]["A2"] = "2026-10"
        workbook.save(self.workbook_path)

        second = import_excel(self.connection, self.workbook_path)
        self.assertNotEqual(first.workbook_id, second.workbook_id)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM workbooks").fetchone()[0], 2)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM roadmap_items").fetchone()[0], 10)

    def test_progress_is_local_and_does_not_replace_source_status(self) -> None:
        import_excel(self.connection, self.workbook_path)
        mission = get_roadmap_items(self.connection, item_type="monthly_mission")[0]

        save_item_progress(
            self.connection,
            mission["item_id"],
            ProgressUpdate(
                status="In progress",
                progress_percent=45,
                date_started="2026-10-31",
                note="Local note, separate from the workbook.",
            ),
        )
        updated = get_roadmap_item(self.connection, mission["item_id"])
        self.assertEqual(updated["status"], "Not Started")
        self.assertEqual(updated["progress_status"], "In progress")
        self.assertEqual(updated["progress_percent"], 45)
        self.assertEqual(updated["progress_date_started"], "2026-10-31")
        self.assertEqual(updated["progress_note"], "Local note, separate from the workbook.")
        source_status = self.connection.execute(
            "SELECT value_json FROM source_cells WHERE sheet_name='Roadmap' AND coordinate='G2'"
        ).fetchone()[0]
        self.assertEqual(source_status, '"Not Started"')
        dashboard = get_dashboard_data(self.connection)
        self.assertEqual(dashboard["roadmap_in_progress"], 1)
        self.assertEqual(dashboard["roadmap_completed"], 0)
        self.assertTrue(import_excel(self.connection, self.workbook_path).already_imported)
        self.assertEqual(get_roadmap_item(self.connection, mission["item_id"])["progress_percent"], 45)

        save_item_progress(
            self.connection,
            mission["item_id"],
            ProgressUpdate(
                status="Completed",
                progress_percent=100,
                date_started="2026-10-31",
                date_completed="2026-11-03",
            ),
        )
        dashboard = get_dashboard_data(self.connection)
        self.assertEqual(dashboard["roadmap_completed"], 1)
        self.assertEqual(dashboard["roadmap_percent"], 100)
        self.assertIsNone(dashboard["current_mission"])

    def test_progress_validation_and_reset(self) -> None:
        import_excel(self.connection, self.workbook_path)
        mission = get_roadmap_items(self.connection, item_type="monthly_mission")[0]
        with self.assertRaisesRegex(ValueError, "100%"):
            save_item_progress(
                self.connection,
                mission["item_id"],
                ProgressUpdate(status="Completed", progress_percent=80),
            )
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            save_item_progress(
                self.connection,
                mission["item_id"],
                ProgressUpdate(status="In progress", progress_percent=20, date_started="2026-2-1"),
            )
        with self.assertRaisesRegex(ValueError, "earlier than"):
            save_item_progress(
                self.connection,
                mission["item_id"],
                ProgressUpdate(
                    status="Completed", progress_percent=100,
                    date_started="2026-11-03", date_completed="2026-11-02",
                ),
            )

        save_item_progress(
            self.connection,
            mission["item_id"],
            ProgressUpdate(status="Blocked", progress_percent=20, note="Waiting on lab access."),
        )
        clear_item_progress(self.connection, mission["item_id"])
        reset = get_roadmap_item(self.connection, mission["item_id"])
        self.assertEqual(reset["progress_status"], "Not started")
        self.assertEqual(reset["progress_percent"], 0)
        self.assertFalse(reset["has_progress_override"])

    def test_progression_uses_source_levels_and_caps_at_last_level(self) -> None:
        import_excel(self.connection, self.workbook_path)
        levels = parse_level_definitions({
            "A14": "Level", "B14": "XP Band", "C14": "Title", "D14": "Unlock", "E14": "Reward",
            "A15": 1, "B15": "0–499", "C15": "IT Apprentice", "D15": "Start", "E15": "Build homelab",
            "A16": 2, "B16": "500–999", "C16": "Network Scout", "D16": "500 XP", "E16": "Network+",
            "A17": 10, "B17": "5,000+", "C17": "Cybersecurity Practitioner", "D17": "5,000 XP", "E17": "Final capstone",
        })
        self.assertEqual([level.level for level in levels], [1, 2, 10])
        at_level_two = calculate_progression(500, levels)
        self.assertEqual(at_level_two["current_level"], 2)
        self.assertEqual(at_level_two["level_title"], "Network Scout")
        at_max = calculate_progression(10_000, levels)
        self.assertEqual(at_max["current_level"], 10)
        self.assertTrue(at_max["is_max_level"])
        self.assertEqual(at_max["next_level_reward"], "")

    def test_source_rewards_award_once_reversal_and_recompletion(self) -> None:
        import_excel(self.connection, self.workbook_path)
        mission = get_roadmap_items(self.connection, item_type="monthly_mission")[0]
        skill = get_roadmap_items(self.connection, item_type="skill")[0]
        project = get_roadmap_items(self.connection, item_type="project")[0]

        initial = get_gamification_data(self.connection)
        self.assertEqual((initial["career_xp"], initial["track_xp"]), (0, 0))
        self.assertEqual(initial["current_level"], 1)

        update_completed = ProgressUpdate(status="Completed", progress_percent=100)
        save_item_progress(self.connection, mission["item_id"], update_completed)
        save_item_progress(self.connection, skill["item_id"], update_completed)
        save_item_progress(self.connection, project["item_id"], update_completed)
        self.assertEqual(sync_xp_awards(self.connection), 0)

        earned = get_gamification_data(self.connection)
        self.assertEqual(earned["career_xp"], 200)
        self.assertEqual(earned["track_xp"], 500)
        self.assertEqual(earned["total_xp"], 700)
        self.assertEqual(earned["current_level"], 3)
        self.assertEqual(earned["awarded_items"], 3)
        self.assertEqual(earned["completed_reward_items"], 3)
        self.assertEqual(earned["xp_available"], 0)

        clear_item_progress(self.connection, mission["item_id"])
        reset = get_gamification_data(self.connection)
        self.assertEqual(reset["career_xp"], 100)
        self.assertEqual(reset["current_level"], 2)
        self.assertEqual(reset["awarded_items"], 2)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM xp_transactions WHERE item_id=?", (mission["item_id"],)
            ).fetchone()[0],
            2,
        )

        save_item_progress(self.connection, mission["item_id"], update_completed)
        restored = get_gamification_data(self.connection)
        self.assertEqual(restored["career_xp"], 200)
        self.assertEqual(restored["total_xp"], 700)
        self.assertEqual(restored["awarded_items"], 3)

    def test_imported_source_completion_awards_without_local_override(self) -> None:
        workbook = load_workbook(self.workbook_path)
        workbook["Projects"]["G2"] = "Done"
        workbook.save(self.workbook_path)
        import_excel(self.connection, self.workbook_path)

        self.assertEqual(sync_xp_awards(self.connection), 1)
        project = get_roadmap_items(self.connection, item_type="project")[0]
        self.assertEqual(project["status"], "Done")
        self.assertEqual(project["progress_status"], "Completed")
        self.assertEqual(project["xp_awarded"], 100)
        data = get_gamification_data(self.connection)
        self.assertEqual(data["career_xp"], 100)
        self.assertEqual(data["current_level"], 2)
        self.assertEqual(sync_xp_awards(self.connection), 0)

    def test_quest_classes_recommendations_and_prerequisite_review(self) -> None:
        workbook = load_workbook(self.workbook_path)
        workbook["Projects"].append([
            "P02", "Final Purple Team Exercise", "Purple Team",
            "Run a final purple-team detection exercise", "Year 3", 1000, "Not Started",
        ])
        starter = workbook["12-Month Starter"]
        for column, value in enumerate((
            "Week 2", "", "Web Security", "PortSwigger Lab Sprint",
            "PortSwigger fundamentals", "Complete the guided labs", "Resource 1", "",
            "Mandatory", 150, "Not Started",
        ), 1):
            starter.cell(8, column, value)
        workbook["My Certifications"]["K25"] = "After Networking"
        workbook.save(self.workbook_path)
        import_excel(self.connection, self.workbook_path)

        quests = get_quest_board(self.connection)
        by_name = {item["name"]: item for item in quests["items"]}
        self.assertEqual(by_name["Network+ / Linux / Git"]["quest_type"], "Main Quest")
        self.assertEqual(by_name["Networking"]["quest_type"], "Side Quest")
        self.assertEqual(by_name["Cisco CCNA"]["quest_type"], "Certification Quest")
        self.assertEqual(by_name["PortSwigger Lab Sprint"]["quest_type"], "Lab Quest")
        self.assertEqual(by_name["Homelab v1"]["quest_type"], "Project Quest")
        self.assertIn("Lab", by_name["Homelab v1"]["quest_tags"])
        self.assertTrue(by_name["Final Purple Team Exercise"]["is_boss_quest"])
        self.assertEqual(by_name["Final Purple Team Exercise"]["xp_reward"], 1000)
        self.assertEqual(by_name["Cisco CCNA"]["quest_readiness"], "Needs review")
        self.assertNotIn(
            by_name["Cisco CCNA"]["item_id"],
            {item["item_id"] for item in quests["recommendations"]},
        )
        self.assertEqual(quests["recommendations"][0]["quest_type"], "Main Quest")
        boss_board = get_quest_board(self.connection, quest_type="Boss Quest")
        self.assertIn("Final Purple Team Exercise", [item["name"] for item in boss_board["items"]])

        self.connection.execute(
            "UPDATE roadmap_items SET prerequisites_json=? WHERE item_id=?",
            (json.dumps(["Networking"]), by_name["Cisco CCNA"]["item_id"]),
        )
        self.connection.commit()
        locked = get_quest_board(self.connection)
        locked_cisco = next(item for item in locked["items"] if item["name"] == "Cisco CCNA")
        self.assertEqual(locked_cisco["quest_readiness"], "Locked")
        self.assertEqual(locked_cisco["missing_prerequisites"][0]["name"], "Networking")

        networking = by_name["Networking"]
        save_item_progress(
            self.connection,
            networking["item_id"],
            ProgressUpdate(status="Completed", progress_percent=100),
        )
        after_dependency = get_quest_board(self.connection)
        cisco_after_dependency = next(
            item for item in after_dependency["items"] if item["name"] == "Cisco CCNA"
        )
        self.assertEqual(cisco_after_dependency["quest_readiness"], "Needs review")
        set_prerequisites_verified(self.connection, cisco_after_dependency["item_id"], True)
        available = get_quest_board(self.connection)
        cisco_available = next(item for item in available["items"] if item["name"] == "Cisco CCNA")
        self.assertEqual(cisco_available["quest_readiness"], "Available")
        recommended = get_recommended_quests(available["items"], limit=30)
        self.assertIn(cisco_available["item_id"], {item["item_id"] for item in recommended})

        set_prerequisites_verified(self.connection, cisco_available["item_id"], False)
        revoked = get_quest_board(self.connection)
        self.assertEqual(
            next(item for item in revoked["items"] if item["name"] == "Cisco CCNA")["quest_readiness"],
            "Needs review",
        )

    def test_skill_tree_uses_workbook_tracks_timing_and_explicit_prerequisites(self) -> None:
        workbook = load_workbook(self.workbook_path)
        workbook["Skill Matrix"].append([
            "Linux", "Foundation", "21", "Bash, permissions, processes", "Not Started", 400,
        ])
        workbook["Skill Matrix"]["G1"] = "Prerequisites"
        workbook["Skill Matrix"]["G3"] = "Networking"
        specializations = workbook["Beyond 25"]
        for column, value in enumerate((
            "Jan-Mar 2032", "Cloud Security", "Azure security",
            "Identity + network + workload security", "Review an Azure lab",
            "azure-review.md", "Azure tools", "High", "Not Started", 500,
        ), 1):
            specializations.cell(5, column, value)
        for column, value in enumerate((
            "Mar-Apr 2032", "Malware Analysis", "Fundamentals", "Static triage",
            "Build an isolated malware-analysis workflow", "malware-static-triage.md",
            "REMnux / PEStudio", "High", "Not Started", 250,
        ), 1):
            specializations.cell(6, column, value)
        workbook.save(self.workbook_path)
        import_excel(self.connection, self.workbook_path)

        tree = get_skill_tree(self.connection)
        self.assertEqual(tree["counts"]["total"], 4)
        self.assertEqual(tree["counts"]["branches"], 3)
        self.assertEqual(tree["counts"]["locked"], 1)
        self.assertEqual(
            {node["name"] for node in tree["items"] if not node["skill_prerequisites"]},
            {"Networking", "Identity + network + workload security", "Static triage"},
        )
        by_name = {node["name"]: node for node in tree["items"]}
        self.assertEqual(by_name["Networking"]["skill_branch"], "Foundation")
        self.assertEqual(by_name["Networking"]["skill_timing_label"], "Target age")
        self.assertEqual(by_name["Networking"]["skill_timing"], "20")
        self.assertEqual(by_name["Static triage"]["skill_branch"], "Malware Analysis")
        self.assertEqual(by_name["Static triage"]["skill_timing_label"], "Timeframe")
        self.assertEqual(by_name["Static triage"]["xp_reward"], 250)
        self.assertIn("REMnux", by_name["Static triage"]["resources_json"])

        locked = get_skill_tree(self.connection)
        linux = next(node for node in locked["items"] if node["name"] == "Linux")
        self.assertEqual(linux["skill_readiness"], "Locked")
        self.assertEqual(linux["skill_missing_prerequisites"][0]["name"], "Networking")

        networking = next(node for node in locked["items"] if node["name"] == "Networking")
        save_item_progress(
            self.connection,
            networking["item_id"],
            ProgressUpdate(status="Completed", progress_percent=100),
        )
        unlocked = get_skill_tree(self.connection)
        linux = next(node for node in unlocked["items"] if node["name"] == "Linux")
        self.assertEqual(linux["skill_readiness"], "Available")
        self.assertEqual(linux["skill_prerequisites"][0]["progress_status"], "Completed")

        filtered = get_skill_tree(self.connection, branch="Malware Analysis", query="REMnux")
        self.assertEqual([node["name"] for node in filtered["items"]], ["Static triage"])

    def test_search_filters_and_year_sort_use_source_fields(self) -> None:
        import_excel(self.connection, self.workbook_path)
        search = get_roadmap_items(self.connection, query="linux")
        self.assertEqual(
            {item["name"] for item in search},
            {"Network+ / Linux / Git", "Homelab v1"},
        )
        skills = get_roadmap_items(
            self.connection,
            item_type="skill",
            category="Foundation",
            sort_by="Phase",
        )
        self.assertEqual([item["name"] for item in skills], ["Networking"])
        completed_source = get_roadmap_items(self.connection, source_status="Completed")
        self.assertIn("CompTIA A+", [item["name"] for item in completed_source])
        year_items = get_roadmap_items(self.connection, year="2026", sort_by="Year")
        self.assertEqual([item["name"] for item in year_items], ["Network+ / Linux / Git"])
        self.assertEqual(get_roadmap_items(self.connection, query="%"), [])

    def test_v1_database_upgrade_preserves_imported_rows(self) -> None:
        import_excel(self.connection, self.workbook_path)
        item_count = self.connection.execute("SELECT COUNT(*) FROM roadmap_items").fetchone()[0]
        source_count = self.connection.execute("SELECT COUNT(*) FROM source_cells").fetchone()[0]
        self.connection.execute("DROP TABLE roadmap_progress")
        self.connection.execute("DROP TABLE xp_transactions")
        self.connection.execute("DROP TABLE quest_prerequisite_reviews")
        self.connection.execute("DELETE FROM schema_migrations WHERE version IN (2, 3, 4)")
        self.connection.commit()
        self.connection.close()

        self.connection = connect_database(self.database_path)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM roadmap_items").fetchone()[0], item_count)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM source_cells").fetchone()[0], source_count)
        self.assertEqual(
            self.connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 4
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='roadmap_progress'").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='xp_transactions'").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='quest_prerequisite_reviews'").fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
