import unittest
from unittest.mock import patch, MagicMock, ANY

import browserstack_appium_percy_ios as app_script


class TestRunActions(unittest.TestCase):
    def test_run_actions_calls_helpers(self):
        driver = MagicMock()
        actions = [
            {"action": "tap", "by": "accessibility_id", "value": "login_button"},
            {"action": "input", "by": "accessibility_id", "value": "username_field", "text": "me@example.com"},
            {"action": "snapshot", "name": "home_screen"},
        ]

        with patch('browserstack_appium_percy_ios.tap') as tap_mock, \
             patch('browserstack_appium_percy_ios.input_text') as input_mock, \
             patch('browserstack_appium_percy_ios.take_snapshot') as snapshot_mock:
            app_script.run_actions(driver, actions)

            tap_mock.assert_called_once()
            input_mock.assert_called_once()
            snapshot_mock.assert_called_once_with(driver, 'home_screen')


class TestSampleLoginFlow(unittest.TestCase):
    def test_sample_login_flow_calls_actions(self):
        driver = MagicMock()

        with patch('browserstack_appium_percy_ios.tap') as tap_mock, \
             patch('browserstack_appium_percy_ios.input_text') as input_mock, \
             patch('browserstack_appium_percy_ios.take_snapshot') as snapshot_mock:
            app_script.sample_login_flow(driver, 'u@test.com', 'secret', snapshot_prefix='test_prefix', wait_after_login=0)

            # login and submit taps should have been called
            self.assertTrue(tap_mock.call_count >= 2)
            # username and password inputs should have been called
            input_mock.assert_any_call(driver, ANY, 'username_field', 'u@test.com')
            input_mock.assert_any_call(driver, ANY, 'password_field', 'secret')
            # snapshot for post-login home should have been requested
            snapshot_mock.assert_any_call(driver, 'test_prefix - home')


class TestBrowserStackStatus(unittest.TestCase):
    def test_set_browserstack_status_executes_script(self):
        driver = MagicMock()
        app_script.set_browserstack_status(driver, 'passed', 'all good')
        driver.execute_script.assert_called_once()
        call_arg = driver.execute_script.call_args[0][0]
        self.assertTrue(call_arg.startswith('browserstack_executor:'))
        self.assertIn('setSessionStatus', call_arg)
        self.assertIn('"status"', call_arg)


if __name__ == '__main__':
    unittest.main()
