import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("LANGSMITH_TRACING", "false")

from gtm_agent import data_service
from gtm_agent.gtm_agent import ProspectScore, build_prospect_profile, score_prospect


class ProspectUpdateTests(unittest.TestCase):
    prospect_id = "LEAD-71001"

    def setUp(self):
        self.original_tech_stack = list(data_service.PROSPECTS[self.prospect_id]["tech_stack"])
        data_service._PROFILES.clear()

    def tearDown(self):
        data_service.PROSPECTS[self.prospect_id]["tech_stack"] = self.original_tech_stack
        data_service._PROFILES.clear()

    def test_update_persists_to_source_record(self):
        data_service.update_prospect_info(self.prospect_id, "Kafka")

        self.assertIn("Kafka", data_service.fetch_tech_stack(self.prospect_id))

    def test_update_invalidates_cached_profile(self):
        before = build_prospect_profile.invoke({"prospect_id": self.prospect_id})

        data_service.update_prospect_info(self.prospect_id, "Kafka")
        after = build_prospect_profile.invoke({"prospect_id": self.prospect_id})

        self.assertNotIn("Kafka", before["prospect_profile"]["tech_stack"])
        self.assertIn("Kafka", after["prospect_profile"]["tech_stack"])

    @patch("gtm_agent.gtm_agent._scoring_llm")
    def test_scoring_uses_updated_source_tech_stack(self, scoring_llm):
        data_service.update_prospect_info(self.prospect_id, "Kafka")
        profile = build_prospect_profile.invoke({"prospect_id": self.prospect_id})["prospect_profile"]
        scoring_llm.invoke.return_value = ProspectScore(
            score=100,
            justification="All required technologies are present.",
            rubric_breakdown={"revenue_fit": 100, "tech_stack_match": 100, "segment_fit": 100},
        )

        score_prospect.invoke({
            "prospect_profile": profile,
            "offering": data_service.get_offering("OFFER-10005"),
        })

        prompt = scoring_llm.invoke.call_args.args[0][1]["content"]
        scored_profile = json.loads(prompt.split("\n\nProspect profile:\n", 1)[1])
        self.assertIn("Kafka", scored_profile["tech_stack"])


if __name__ == "__main__":
    unittest.main()
