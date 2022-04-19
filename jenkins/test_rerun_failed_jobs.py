from os import dup
import unittest
import rerun_failed_jobs


class TestFilters(unittest.TestCase):
    def test_components_true(self):
        class TestOptions:
            components = ["xdcr"]
            subcomponents = None
            exclude_components = None

        options = TestOptions()
        job = {
            "component": "QUERY"
        }
        parameters = {
            "component": "xdcr"
        }

        self.assertTrue(rerun_failed_jobs.passes_component_filter(
            job, parameters, options))

    def test_components_false(self):
        class TestOptions:
            components = None
            subcomponents = None
            exclude_components = ["xdcr"]

        options = TestOptions()
        job = {
            "component": "XDCR"
        }
        parameters = {
            "component": "xdcr"
        }

        self.assertFalse(rerun_failed_jobs.passes_component_filter(
            job, parameters, options))


class TestDuplicates(unittest.TestCase):
    def test_get_duplicate_jobs(self):
        class TestOptions:
            jenkins_url = "http://qa.sc.couchbase.com"

        options = TestOptions()
        parameters = {
            "component": "aa",
            "subcomponent": "bb",
            "version_number": "7.0.0-3874",
            "dispatcher_params": {
                "dispatcher_url": "http://qa.sc.couchbase.com/job/test_suite_dispatcher/",
                "OS": "centos"
            },
            "os": "centos"
        }
        job_name = "test_suite_executor"

        tests = [
            [0, "different_name", "aa", "bb", "7.0.0-3875"],
            [0, "test_suite_executor", "dd", "bb", "7.0.0-3874"],
            [0, "test_suite_executor", "aa", "ee", "7.0.0-3874"],
            [0, "test_suite_dispatcher_dynvm", "aa", "bb", "7.0.0-3874"],
            [0, "test_suite_dispatcher", "dd", "bb", "7.0.0-3874"],
            [0, "test_suite_dispatcher", "aa", "ee,ff", "7.0.0-3874"],
            [1, "test_suite_executor", "aa", "bb", "7.0.0-3874"],
            [1, "test_suite_dispatcher", "aa", "bb", "7.0.0-3874"],
            [1, "test_suite_dispatcher", "aa", "bb,cc", "7.0.0-3874"],
            [1, "test_suite_dispatcher", "aa", "None", "7.0.0-3874"],
            [1, "test_suite_dispatcher", "aa", "", "7.0.0-3874"],
            [1, "test_suite_dispatcher_multiple_pools", "aa", "bb", "7.0.0-3874"]
        ]

        for [expected_duplicates, name, component, subcomponent, version_number] in tests:
            running_builds = [
                {
                    "name": name,
                    "parameters": {
                        "component": component,
                        "subcomponent": subcomponent,
                        "version_number": version_number
                    }
                }
            ]
            if "dispatcher" in name:
                running_builds[0]["parameters"]["OS"] = "centos"
            else:
                running_builds[0]["parameters"]["os"] = "centos"
            duplicates = rerun_failed_jobs.get_duplicate_jobs(
                running_builds, job_name, parameters, options)
            self.assertTrue(len(duplicates) == expected_duplicates)


class TestRerunWorseHelper(unittest.TestCase):
    def test_rerun_worse_helper(self):
        # expected_result, max_failed_reruns, [total_count, fail_count, result]...
        tests = [
            [False, 1, [0, 0, "FAILURE"]],
            [False, 1, [0, 0, "FAILURE"], [1, 0, "SUCCESS"]],
            [False, 1, [0, 0, "FAILURE"], [2, 2, "UNSTABLE"]],
            [True, 1, [2, 1, "UNSTABLE"], [2, 2, "UNSTABLE"]],
            [True, 1, [2, 1, "UNSTABLE"], [0, 0, "FAILURE"]],
            [True, 1, [2, 1, "UNSTABLE"], [0, 0, "FAILURE"]],
            [True, 1, [3, 2, "UNSTABLE"], [3, 1, "UNSTABLE"], [0, 0, "FAILURE"]],
            [False, 1, [2, 1, "UNSTABLE"], [0, 0, "FAILURE"], [0, 0, "FAILURE"]],
            [True, 2, [2, 1, "UNSTABLE"], [0, 0, "FAILURE"], [0, 0, "FAILURE"]],

        ]

        for test in tests:
            result = test[0]
            class TestOptions:
                max_failed_reruns = test[1]

            options = TestOptions()
            all_runs = [{"totalCount": run[0], "failCount": run[1], "result": run[2]} for run in reversed(test[2:])]
            self.assertEqual(result, rerun_failed_jobs.rerun_worse_helper(all_runs, options))


if __name__ == '__main__':
    unittest.main()
