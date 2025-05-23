import unittest
from unittest.mock import patch, Mock, call
import subprocess
import os
import json
import base64

# Assuming api.data_pipeline contains the functions to be tested
from api.data_pipeline import download_repo, get_azuredevops_file_content, DatabaseManager, get_file_content
from adalflow.utils import get_adalflow_default_root_path

class TestAzureDevOpsIntegration(unittest.TestCase):

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.listdir')
    def test_download_repo_azuredevops_with_pat(self, mock_listdir, mock_makedirs, mock_exists, mock_subprocess_run):
        """Test download_repo for Azure DevOps with a PAT."""
        mock_exists.return_value = False  # Ensure it attempts to clone
        mock_listdir.return_value = [] # Repo directory is empty
        mock_subprocess_run.return_value = Mock(stdout=b"Cloned successfully", stderr=b"", returncode=0)

        repo_url = "https://dev.azure.com/org/project/_git/repo_name"
        local_path = "/tmp/repo_name"
        access_token = "test_pat"
        
        download_repo(repo_url, local_path, type="azuredevops", access_token=access_token)

        expected_clone_url = f"https://{access_token}@dev.azure.com/org/project/_git/repo_name"
        mock_subprocess_run.assert_any_call(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_subprocess_run.assert_any_call(['git', 'clone', expected_clone_url, local_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_makedirs.assert_called_with(local_path, exist_ok=True)

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.listdir')
    def test_download_repo_azuredevops_no_pat(self, mock_listdir, mock_makedirs, mock_exists, mock_subprocess_run):
        """Test download_repo for Azure DevOps without a PAT."""
        mock_exists.return_value = False
        mock_listdir.return_value = []
        mock_subprocess_run.return_value = Mock(stdout=b"Cloned successfully", stderr=b"", returncode=0)

        repo_url = "https://org.visualstudio.com/project/_git/repo_name"
        local_path = "/tmp/repo_name"
        
        download_repo(repo_url, local_path, type="azuredevops", access_token=None)

        # When no PAT, clone_url should be the same as repo_url
        mock_subprocess_run.assert_any_call(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_subprocess_run.assert_any_call(['git', 'clone', repo_url, local_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_makedirs.assert_called_with(local_path, exist_ok=True)

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.listdir')
    def test_download_repo_azuredevops_called_process_error(self, mock_listdir, mock_makedirs, mock_exists, mock_subprocess_run):
        """Test download_repo for Azure DevOps handles CalledProcessError."""
        mock_exists.return_value = False
        mock_listdir.return_value = []
        # Simulate git clone failing
        mock_subprocess_run.side_effect = [
            Mock(stdout=b"git version 2.0.0", stderr=b"", returncode=0), # for git --version
            subprocess.CalledProcessError(cmd=['git', 'clone', 'url', 'path'], returncode=128, stderr=b"fatal: repository 'url' not found")
        ]
        
        repo_url = "https://dev.azure.com/org/project/_git/repo_name_nonexistent"
        local_path = "/tmp/nonexistent_repo"
        access_token = "test_pat"

        with self.assertRaises(ValueError) as context:
            download_repo(repo_url, local_path, type="azuredevops", access_token=access_token)
        
        self.assertIn("Error during cloning: fatal: repository 'url' not found", str(context.exception))
        expected_clone_url = f"https://{access_token}@dev.azure.com/org/project/_git/repo_name_nonexistent"
        
        calls = [
            call(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE),
            call(['git', 'clone', expected_clone_url, local_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ]
        mock_subprocess_run.assert_has_calls(calls)

    @patch('subprocess.run')
    def test_get_azuredevops_file_content_direct_content(self, mock_subprocess_run):
        """Test get_azuredevops_file_content with direct content in response."""
        repo_url = "https://dev.azure.com/myorg/myproject/_git/myrepo"
        file_path = "src/main.py"
        access_token = "test_pat_token"
        
        mock_response_json = {
            "content": "print('Hello, Azure DevOps!')",
            "isFolder": False
        }
        mock_subprocess_run.return_value = Mock(
            stdout=json.dumps(mock_response_json).encode('utf-8'),
            stderr=b"",
            returncode=0
        )
        
        content = get_azuredevops_file_content(repo_url, file_path, access_token)
        self.assertEqual(content, "print('Hello, Azure DevOps!')")

        expected_api_url_part = "https://dev.azure.com/myorg/myproject/_apis/git/repositories/myrepo/items"
        # Check that the path and includeContent are in the call arguments
        called_args, _ = mock_subprocess_run.call_args
        self.assertIn(expected_api_url_part, called_args[0][-1]) # Last arg is the URL
        self.assertIn(f"path={file_path}", called_args[0][-1])
        self.assertIn("includeContent=true", called_args[0][-1])
        
        # Check for auth header
        expected_auth_header = base64.b64encode(f":{access_token}".encode()).decode()
        self.assertIn("-H", called_args[0])
        self.assertIn(f"Authorization: Basic {expected_auth_header}", " ".join(called_args[0]))


    @patch('subprocess.run')
    def test_get_azuredevops_file_content_download_url(self, mock_subprocess_run):
        """Test get_azuredevops_file_content with downloadUrl in response."""
        repo_url = "https://myorg.visualstudio.com/myproject/_git/anotherrepo"
        file_path = "README.md"
        access_token = "another_pat"

        download_url = "https://codedownload.azure.com/content"
        mock_initial_response_json = {
            "downloadUrl": download_url,
            "isFolder": False
        }
        mock_download_response_content = "# Test Readme"

        # Simulate two calls to subprocess.run: 1. for API, 2. for downloadUrl
        mock_subprocess_run.side_effect = [
            Mock(stdout=json.dumps(mock_initial_response_json).encode('utf-8'), stderr=b"", returncode=0), # API call
            Mock(stdout=mock_download_response_content.encode('utf-8'), stderr=b"", returncode=0)  # Download call
        ]

        content = get_azuredevops_file_content(repo_url, file_path, access_token)
        self.assertEqual(content, mock_download_response_content)

        expected_api_url_part = "https://dev.azure.com/myorg/myproject/_apis/git/repositories/anotherrepo/items"
        
        # Check first call (API)
        first_call_args, _ = mock_subprocess_run.call_args_list[0]
        self.assertIn(expected_api_url_part, first_call_args[0][-1])
        self.assertIn(f"path={file_path}", first_call_args[0][-1])
        expected_auth_header = base64.b64encode(f":{access_token}".encode()).decode()
        self.assertIn(f"Authorization: Basic {expected_auth_header}", " ".join(first_call_args[0]))

        # Check second call (downloadUrl)
        second_call_args, _ = mock_subprocess_run.call_args_list[1]
        self.assertEqual(second_call_args[0][-1], download_url) # URL should be the download_url
        self.assertIn(f"Authorization: Basic {expected_auth_header}", " ".join(second_call_args[0]))


    @patch('subprocess.run')
    def test_get_azuredevops_file_content_api_error_404(self, mock_subprocess_run):
        """Test get_azuredevops_file_content handling a 404 API error."""
        repo_url = "https://dev.azure.com/org/project/_git/repo"
        file_path = "nonexistent.txt"
        access_token = "pat"

        # Simulate curl error with stderr (typical for HTTP 404 from curl)
        # and an Azure DevOps JSON error message in stdout
        error_json_response = {
            "message": "TF401019: The Git item you are looking for could not be found."
        }
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            cmd=['curl', '...'], 
            returncode=22, # curl's http error code
            stdout=json.dumps(error_json_response).encode('utf-8'), # Azure DevOps often puts JSON error in stdout
            stderr=b"curl: (22) The requested URL returned error: 404"
        )

        with self.assertRaises(ValueError) as context:
            get_azuredevops_file_content(repo_url, file_path, access_token)
        self.assertIn("Azure DevOps API error: TF401019: The Git item you are looking for could not be found.", str(context.exception))

    @patch('subprocess.run')
    def test_get_azuredevops_file_content_invalid_json_response(self, mock_subprocess_run):
        """Test get_azuredevops_file_content with invalid JSON response."""
        repo_url = "https://dev.azure.com/org/project/_git/repo"
        file_path = "file.txt"
        access_token = "pat"

        mock_subprocess_run.return_value = Mock(
            stdout=b"This is not JSON", # Invalid JSON
            stderr=b"",
            returncode=0
        )

        with self.assertRaises(ValueError) as context:
            get_azuredevops_file_content(repo_url, file_path, access_token)
        self.assertIn("Invalid JSON response from Azure DevOps API", str(context.exception))

    @patch('subprocess.run')
    def test_get_azuredevops_file_content_is_folder(self, mock_subprocess_run):
        """Test get_azuredevops_file_content when path is a folder."""
        repo_url = "https://dev.azure.com/myorg/myproject/_git/myrepo"
        file_path = "src/" # Path is a folder
        access_token = "test_pat_token"
        
        mock_response_json = {
            "isFolder": True,
            # Other folder metadata might be here
        }
        mock_subprocess_run.return_value = Mock(
            stdout=json.dumps(mock_response_json).encode('utf-8'),
            stderr=b"",
            returncode=0
        )
        
        with self.assertRaises(ValueError) as context:
            get_azuredevops_file_content(repo_url, file_path, access_token)
        self.assertIn(f"Path '{file_path}' is a directory, not a file.", str(context.exception))
        
    @patch('subprocess.run')
    def test_get_azuredevops_file_content_unsupported_url_structure(self, mock_subprocess_run):
        """Test with an Azure DevOps URL that doesn't match expected formats."""
        repo_url = "https://unsupported.azure.com/myorg/myproject/_git/myrepo" # Invalid domain for parsing
        file_path = "src/main.py"
        access_token = "test_pat_token"
        
        with self.assertRaises(ValueError) as context:
            get_azuredevops_file_content(repo_url, file_path, access_token)
        self.assertIn("Not a valid Azure DevOps repository URL", str(context.exception))

        repo_url_bad_format = "https://dev.azure.com/myorg/_git/myrepo" # Missing project segment
        with self.assertRaises(ValueError) as context:
            get_azuredevops_file_content(repo_url_bad_format, file_path, access_token)
        self.assertIn("Invalid Azure DevOps URL format.", str(context.exception))

        repo_url_vs_bad_format = "https://myorg.visualstudio.com/_git/" # Missing project and repo
        with self.assertRaises(ValueError) as context:
            get_azuredevops_file_content(repo_url_vs_bad_format, file_path, access_token)
        self.assertIn("Invalid Azure DevOps URL format for visualstudio.com.", str(context.exception))

    @patch('api.data_pipeline.download_repo')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.listdir') 
    @patch('adalflow.utils.get_adalflow_default_root_path')
    def test_database_manager_create_repo_azuredevops_dev_azure_url(self, mock_get_root, mock_listdir, mock_exists, mock_makedirs, mock_download_repo):
        """Test DatabaseManager._create_repo with a dev.azure.com URL."""
        mock_get_root.return_value = "/fake/adalflow/root"
        mock_exists.return_value = False # Simulate repo not existing locally
        mock_listdir.return_value = [] # Simulate repo directory is empty

        db_manager = DatabaseManager()
        repo_url = "https://dev.azure.com/myorg/myproject/_git/mycoolrepo"
        access_token = "my_pat"
        
        db_manager._create_repo(repo_url, type="azuredevops", access_token=access_token)

        expected_repo_name = "mycoolrepo"
        expected_save_repo_dir = f"/fake/adalflow/root/repos/{expected_repo_name}"
        
        mock_download_repo.assert_called_once_with(repo_url, expected_save_repo_dir, "azuredevops", access_token)
        mock_makedirs.assert_any_call(expected_save_repo_dir, exist_ok=True)
        mock_makedirs.assert_any_call(f"/fake/adalflow/root/databases", exist_ok=True)
        self.assertEqual(db_manager.repo_paths["save_repo_dir"], expected_save_repo_dir)
        self.assertEqual(db_manager.repo_paths["save_db_file"], f"/fake/adalflow/root/databases/{expected_repo_name}.pkl")

    @patch('api.data_pipeline.download_repo')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('adalflow.utils.get_adalflow_default_root_path')
    def test_database_manager_create_repo_azuredevops_visualstudio_url(self, mock_get_root, mock_listdir, mock_exists, mock_makedirs, mock_download_repo):
        """Test DatabaseManager._create_repo with a visualstudio.com URL."""
        mock_get_root.return_value = "/test/adalflow"
        mock_exists.return_value = True # Simulate repo exists
        mock_listdir.return_value = ["some_file.txt"] # Simulate repo is not empty

        db_manager = DatabaseManager()
        repo_url = "https://myotherorg.visualstudio.com/anotherproject/_git/anotherrepo.git" # With .git suffix
        
        db_manager._create_repo(repo_url, type="azuredevops", access_token=None)

        expected_repo_name = "anotherrepo" # .git should be stripped
        expected_save_repo_dir = f"/test/adalflow/repos/{expected_repo_name}"
        
        # download_repo should NOT be called if os.listdir returns non-empty
        mock_download_repo.assert_not_called()
        mock_makedirs.assert_any_call(expected_save_repo_dir, exist_ok=True)
        self.assertEqual(db_manager.repo_paths["save_repo_dir"], expected_save_repo_dir)

    @patch('api.data_pipeline.download_repo')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('adalflow.utils.get_adalflow_default_root_path')
    def test_database_manager_create_repo_azuredevops_url_type_detection(self, mock_get_root, mock_listdir, mock_exists, mock_makedirs, mock_download_repo):
        """Test DatabaseManager._create_repo with Azure DevOps URL and type detection."""
        mock_get_root.return_value = "/fake/root"
        mock_exists.return_value = False
        mock_listdir.return_value = []

        db_manager = DatabaseManager()
        # type is not explicitly "azuredevops", it should be detected
        repo_url = "https://dev.azure.com/detected_org/detected_project/_git/detected_repo"
        
        db_manager._create_repo(repo_url, access_token="detected_pat") # No type specified

        expected_repo_name = "detected_repo"
        expected_save_repo_dir = f"/fake/root/repos/{expected_repo_name}"
        
        # The crucial part: type="azuredevops" should be passed to download_repo
        mock_download_repo.assert_called_once_with(repo_url, expected_save_repo_dir, "azuredevops", "detected_pat")
        self.assertEqual(db_manager.repo_url_or_path, repo_url)

    @patch('api.data_pipeline.download_repo')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('adalflow.utils.get_adalflow_default_root_path')
    def test_database_manager_create_repo_azuredevops_different_url_structures(self, mock_get_root, mock_listdir, mock_exists, mock_makedirs, mock_download_repo):
        """Test _create_repo with slightly different but valid Azure DevOps URL structures."""
        mock_get_root.return_value = "/base"
        mock_exists.return_value = False
        mock_listdir.return_value = []
        db_manager = DatabaseManager()

        urls_and_names = {
            "https://dev.azure.com/org/proj/_git/repo1": "repo1",
            "https://org.visualstudio.com/proj/_git/repo2.git": "repo2",
            "https://special-org.visualstudio.com/DefaultCollection/project/_git/repo3": "repo3", # DefaultCollection often in older URLs
            "https://dev.azure.com/org-with-hyphen/proj-with-dot.case/_git/RepoWithCase": "RepoWithCase",
        }

        for i, (url, expected_name) in enumerate(urls_and_names.items()):
            with self.subTest(url=url):
                db_manager._create_repo(url, type="azuredevops", access_token=f"token_{i}")
                expected_save_dir = f"/base/repos/{expected_name}"
                mock_download_repo.assert_called_with(url, expected_save_dir, "azuredevops", f"token_{i}")
                self.assertEqual(db_manager.repo_paths["save_repo_dir"], expected_save_dir)
                self.assertEqual(db_manager.repo_paths["save_db_file"], f"/base/databases/{expected_name}.pkl")
                # Reset for next subtest iteration if needed, or ensure mocks are reset if using instance-level manager
                db_manager.reset_database() # Reset paths for the next iteration
                mock_exists.return_value = False # Reset for next iteration
                mock_listdir.return_value = [] # Reset for next iteration


if __name__ == '__main__':
    unittest.main()
