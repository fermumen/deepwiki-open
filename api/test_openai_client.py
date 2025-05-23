import unittest
from unittest.mock import patch, Mock, call
import os

# Assuming api.openai_client contains the class to be tested
from api.openai_client import OpenAIClient
from openai import OpenAI, AsyncOpenAI, AzureOpenAI, AsyncAzureOpenAI

class TestOpenAIClientInitialization(unittest.TestCase):

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_api_key"})
    @patch('api.openai_client.OpenAI')
    @patch('api.openai_client.AsyncOpenAI')
    def test_initializes_standard_openai_client_default_url(self, MockAsyncOpenAI, MockOpenAI):
        """Test initialization with default OpenAI URL."""
        client = OpenAIClient()
        MockOpenAI.assert_called_once_with(api_key="test_api_key", base_url="https://api.openai.com/v1")
        
        # Check async client initialization (it's lazy, so call a method that initializes it)
        client.init_async_client()
        MockAsyncOpenAI.assert_called_once_with(api_key="test_api_key", base_url="https://api.openai.com/v1")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_api_key", "OPENAI_BASE_URL": "https://custom.openai.com/v1"})
    @patch('api.openai_client.OpenAI')
    @patch('api.openai_client.AsyncOpenAI')
    def test_initializes_standard_openai_client_custom_url_env(self, MockAsyncOpenAI, MockOpenAI):
        """Test initialization with custom OpenAI URL from environment variable."""
        client = OpenAIClient()
        MockOpenAI.assert_called_once_with(api_key="test_api_key", base_url="https://custom.openai.com/v1")
        client.init_async_client()
        MockAsyncOpenAI.assert_called_once_with(api_key="test_api_key", base_url="https://custom.openai.com/v1")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_api_key"})
    @patch('api.openai_client.OpenAI')
    @patch('api.openai_client.AsyncOpenAI')
    def test_initializes_standard_openai_client_custom_url_arg(self, MockAsyncOpenAI, MockOpenAI):
        """Test initialization with custom OpenAI URL as argument, overriding env."""
        custom_url = "https://another.openai.com/v1"
        client = OpenAIClient(base_url=custom_url)
        MockOpenAI.assert_called_once_with(api_key="test_api_key", base_url=custom_url)
        client.init_async_client()
        MockAsyncOpenAI.assert_called_once_with(api_key="test_api_key", base_url=custom_url)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "key_from_env"})
    @patch('api.openai_client.OpenAI')
    def test_uses_direct_api_key_over_env(self, MockOpenAI):
        """Test that directly passed API key overrides environment variable."""
        direct_key = "direct_test_key"
        client = OpenAIClient(api_key=direct_key)
        MockOpenAI.assert_called_once_with(api_key=direct_key, base_url="https://api.openai.com/v1")

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "azure_test_key",
        "AZURE_OPENAI_API_VERSION": "2024-02-15-preview" 
    })
    @patch('api.openai_client.AzureOpenAI')
    @patch('api.openai_client.AsyncAzureOpenAI')
    def test_initializes_azure_client_for_azure_url(self, MockAsyncAzureOpenAI, MockAzureOpenAI):
        """Test initialization with an Azure OpenAI URL."""
        azure_url = "https://my-azure-openai.openai.azure.com"
        client = OpenAIClient(base_url=azure_url)
        
        MockAzureOpenAI.assert_called_once_with(
            api_key="azure_test_key",
            azure_endpoint=azure_url,
            api_version="2024-02-15-preview"
        )
        # Check async client initialization
        client.init_async_client()
        MockAsyncAzureOpenAI.assert_called_once_with(
            api_key="azure_test_key",
            azure_endpoint=azure_url,
            api_version="2024-02-15-preview"
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "azure_key_no_version"}) # AZURE_OPENAI_API_VERSION not set
    @patch('api.openai_client.AzureOpenAI')
    @patch('api.openai_client.AsyncAzureOpenAI')
    def test_initializes_azure_client_default_api_version(self, MockAsyncAzureOpenAI, MockAzureOpenAI):
        """Test Azure client initialization uses default API version if not set in env."""
        azure_url = "https://another-azure.openai.azure.com"
        client = OpenAIClient(base_url=azure_url)
        
        default_version = "2023-07-01-preview" # Default from OpenAIClient
        MockAzureOpenAI.assert_called_once_with(
            api_key="azure_key_no_version",
            azure_endpoint=azure_url,
            api_version=default_version
        )
        client.init_async_client()
        MockAsyncAzureOpenAI.assert_called_once_with(
            api_key="azure_key_no_version",
            azure_endpoint=azure_url,
            api_version=default_version
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "another_azure_key"})
    @patch('api.openai_client.AzureOpenAI')
    def test_azure_client_custom_api_version_env_name(self, MockAzureOpenAI):
        """Test Azure client with custom environment variable name for API version."""
        azure_url = "https://custom-version-azure.openai.azure.com"
        custom_env_var_name = "MY_CUSTOM_AZURE_VERSION"
        custom_version = "2025-01-01"

        with patch.dict(os.environ, {custom_env_var_name: custom_version}):
            client = OpenAIClient(base_url=azure_url, env_azure_api_version_name=custom_env_var_name)
        
        MockAzureOpenAI.assert_called_once_with(
            api_key="another_azure_key",
            azure_endpoint=azure_url,
            api_version=custom_version
        )

    @patch.dict(os.environ, {}, clear=True) # Ensure OPENAI_API_KEY is not set
    @patch('api.openai_client.OpenAI') # Mock to prevent actual client init
    def test_raises_value_error_if_api_key_is_missing(self, MockOpenAI):
        """Test that ValueError is raised if OPENAI_API_KEY is not set and not provided directly."""
        with self.assertRaises(ValueError) as context:
            OpenAIClient() # No API key provided directly or in env
        self.assertIn("Environment variable OPENAI_API_KEY must be set", str(context.exception))
        MockOpenAI.assert_not_called() # Client should not be initialized

if __name__ == '__main__':
    unittest.main()
