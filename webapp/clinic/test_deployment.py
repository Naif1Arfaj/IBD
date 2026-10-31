import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class HostedDemoBootstrapTests(TestCase):
    @patch("clinic.management.commands.bootstrap_demo.call_command")
    def test_requires_password_before_any_database_initialisation(self, initialise):
        with patch.dict(os.environ, {"DEMO_NURSE_PASSWORD": ""}):
            with self.assertRaises(CommandError):
                call_command("bootstrap_demo")
        initialise.assert_not_called()

    @patch("clinic.management.commands.bootstrap_demo.call_command")
    def test_repeat_startup_preserves_user_and_does_not_print_password(self, initialise):
        output = StringIO()
        password = "test-only-hosted-demo-password"
        with patch.dict(os.environ, {"DEMO_NURSE_PASSWORD": password}):
            call_command("bootstrap_demo", stdout=output)
            first = get_user_model().objects.get(username="nurse")
            call_command("bootstrap_demo", stdout=output)
        user = get_user_model().objects.get(username="nurse")
        self.assertEqual(first.pk, user.pk)
        self.assertEqual(first.password, user.password)
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotIn(password, output.getvalue())
        self.assertEqual(initialise.call_count, 4)
