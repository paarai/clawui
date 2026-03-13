"""Tests for GitHub integration tool."""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path so we can import src.* as top-level packages
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent import create_tools, execute_tool
from src.github_integration import create_github_repo


class TestGithubIntegration(unittest.TestCase):

    def test_tool_registered(self):
        """Check that github_create_repo tool is present."""
        tools = create_tools()
        names = [t['name'] for t in tools]
        self.assertIn('github_create_repo', names)

    def test_tool_schema(self):
        """Check that the tool has proper input schema."""
        tools = create_tools()
        tool = next(t for t in tools if t['name'] == 'github_create_repo')
        self.assertIn('repo_name', tool['input_schema']['properties'])
        self.assertIn('repo_desc', tool['input_schema']['properties'])
        self.assertEqual(tool['input_schema']['required'], ['repo_name'])

    def test_execute_missing_repo_name(self):
        """Test tool execution with missing repo_name."""
        result = execute_tool('github_create_repo', {})
        self.assertIn('Missing', result.get('text', ''))

    def test_execute_with_mock_token_success(self):
        """Test successful repo creation via mocked API token."""
        with patch('src.github_integration.get_github_token') as mock_token, \
             patch('src.github_integration.create_repo_via_api') as mock_api:
            mock_token.return_value = 'fake-token'
            mock_api.return_value = (True, None, 'https://github.com/user/test-repo')
            result = execute_tool('github_create_repo', {'repo_name': 'test-repo'})
            self.assertIn('✅', result.get('text', ''))
            self.assertIn('via api', result.get('text', '').lower())

    def test_execute_with_mock_gh_success(self):
        """Test successful repo creation via mocked gh CLI."""
        with patch('src.github_integration.get_github_token') as mock_token, \
             patch('src.github_integration.is_gh_authenticated') as mock_gh_auth, \
             patch('src.github_integration.create_repo_via_gh_cli') as mock_gh:
            mock_token.return_value = None
            mock_gh_auth.return_value = True
            mock_gh.return_value = (True, None, 'https://github.com/user/test-repo')
            result = execute_tool('github_create_repo', {'repo_name': 'test-repo'})
            self.assertIn('✅', result.get('text', ''))
            self.assertIn('via gh', result.get('text', '').lower())

    def test_execute_with_mock_cdp_success(self):
        """Test successful repo creation via mocked CDP."""
        with patch('src.github_integration.get_github_token') as mock_token, \
             patch('src.github_integration.is_gh_authenticated') as mock_gh_auth, \
             patch('src.github_integration._ensure_cdp_client') as mock_cdp_client, \
             patch('src.github_integration.create_repo_via_cdp') as mock_cdp:
            mock_token.return_value = None
            mock_gh_auth.return_value = False
            mock_client = MagicMock()
            mock_cdp_client.return_value = mock_client
            mock_cdp.return_value = (True, None, 'https://github.com/user/test-repo')
            result = execute_tool('github_create_repo', {'repo_name': 'test-repo'})
            self.assertIn('✅', result.get('text', ''))
            self.assertIn('via cdp', result.get('text', '').lower())

    def test_execute_all_methods_fail(self):
        """Test failure when all methods fail."""
        with patch('src.github_integration.get_github_token') as mock_token, \
             patch('src.github_integration.is_gh_authenticated') as mock_gh_auth, \
             patch('src.github_integration._ensure_cdp_client') as mock_cdp_client:
            mock_token.return_value = None
            mock_gh_auth.return_value = False
            mock_cdp_client.return_value = None
            result = execute_tool('github_create_repo', {'repo_name': 'test-repo'})
            self.assertIn('❌', result.get('text', ''))

    def test_create_github_repo_function_direct(self):
        """Direct function test with all methods failing (mocked)."""
        with patch('src.github_integration.get_github_token') as mock_token, \
             patch('src.github_integration.is_gh_authenticated') as mock_gh_auth, \
             patch('src.github_integration._ensure_cdp_client') as mock_cdp_client:
            mock_token.return_value = None
            mock_gh_auth.return_value = False
            mock_cdp_client.return_value = None
            result = create_github_repo('some-repo')
            self.assertFalse(result['success'])
            self.assertIsNone(result['method'])
            self.assertIsNotNone(result['error'])


if __name__ == '__main__':
    unittest.main()
