import unittest
import hanging_jobs

class HangingJobsTest(unittest.TestCase):

    def test_parse_components(self):
        components = hanging_jobs.parse_components("component1:subcomponent1,subcomponent2 component2:subcomponent3 component3")
        self.assertEqual(components, {"component1": ["subcomponent1", "subcomponent2"], "component2": ["subcomponent3"], "component3": None})

if __name__ == "__main__":
    unittest.main()
