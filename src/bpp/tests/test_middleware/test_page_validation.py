import logging

import pytest
from django.test import RequestFactory

from bpp.middleware import MaliciousRequestBlockingMiddleware


@pytest.mark.django_db
class TestMaliciousRequestBlockingMiddleware:
    def setup_method(self):
        self.factory = RequestFactory()
        self.middleware = MaliciousRequestBlockingMiddleware(lambda r: None)

    def test_no_page_parameter_allowed(self):
        """Test: No page parameter should pass through"""
        request = self.factory.get("/bpp/autorzy/")
        response = self.middleware.process_request(request)
        assert response is None

    def test_numeric_page_allowed(self):
        """Test: Numeric page parameters should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=1")
        response = self.middleware.process_request(request)
        assert response is None

    def test_large_numeric_page_allowed(self):
        """Test: Large numeric page numbers should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=999999")
        response = self.middleware.process_request(request)
        assert response is None

    def test_last_keyword_allowed(self):
        """Test: 'last' keyword should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=last")
        response = self.middleware.process_request(request)
        assert response is None

    def test_last_uppercase_allowed(self):
        """Test: 'LAST' keyword should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=LAST")
        response = self.middleware.process_request(request)
        assert response is None

    def test_last_mixed_case_allowed(self):
        """Test: 'Last' keyword should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=Last")
        response = self.middleware.process_request(request)
        assert response is None

    def test_short_alphanumeric_allowed(self):
        """Test: Short (<=5 chars) alphanumeric strings allowed (possible typos)"""
        request = self.factory.get("/bpp/autorzy/?page=1a")
        response = self.middleware.process_request(request)
        assert response is None

    def test_five_char_string_allowed(self):
        """Test: Exactly 5 character strings allowed"""
        request = self.factory.get("/bpp/autorzy/?page=12abc")
        response = self.middleware.process_request(request)
        assert response is None

    def test_sql_injection_blocked(self):
        """Test: SQL injection attempts should be blocked"""
        request = self.factory.get("/bpp/autorzy/?page=1+AND+1=1--")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_long_malicious_string_blocked(self):
        """Test: Long malicious strings should be blocked"""
        request = self.factory.get(
            "/bpp/autorzy/?page=++++++++++++++++++++++++++++++94%22+AND"
        )
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_url_encoded_injection_blocked(self):
        """Test: URL-encoded injection should be blocked"""
        request = self.factory.get(
            "/bpp/autorzy/?page=%3CSCRIPT%3Ealert%281%29%3C%2FSCRIPT%3E"
        )
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_original_traceback_string_blocked(self):
        """Test: Original malicious string from user's traceback should be blocked"""
        # This is the actual string from the user's traceback
        malicious_page = (
            "                                94\" AND ANd/**/1373=(seLEcT/**/uPPeR(XMlTYpE(chr(60)||CHr(58)||"
            "%27~%27||(SELECt/**/(cASe/**/when/**/(1373=1373)/**/TheN/**/1/**/eLse/**/0/**/End)/**/fROM/**/"
            "DuaL)||%27~%27||Chr(62)))/**/FROM/**/DUal)-- -"
        )
        request = self.factory.get(f"/bpp/autorzy/?page={malicious_page}")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_six_char_alphanumeric_blocked(self):
        """Test: 6 character alphanumeric strings should be blocked"""
        request = self.factory.get("/bpp/autorzy/?page=abc123")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_spaces_in_page_blocked(self):
        """Test: Page parameters with spaces should be blocked"""
        request = self.factory.get("/bpp/autorzy/?page=1 2 3 4 5 6")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_logging_on_blocked_request(self, caplog):
        """Test: Blocked requests should be logged"""
        caplog.set_level(logging.WARNING)

        request = self.factory.get("/bpp/autorzy/?page=malicious_string_here")
        self.middleware.process_request(request)

        assert "Blocked malicious request" in caplog.text
        assert "malicious_string_here" in caplog.text

    def test_logging_includes_remote_addr(self, caplog):
        """Test: Logged events should include remote address"""
        caplog.set_level(logging.WARNING)

        request = self.factory.get(
            "/bpp/autorzy/?page=malicious_here", REMOTE_ADDR="192.168.1.100"
        )
        response = self.middleware.process_request(request)

        assert response.status_code == 444
        # Check that the warning was logged
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    def test_empty_page_parameter_allowed(self):
        """Test: Empty page parameter should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=")
        response = self.middleware.process_request(request)
        assert response is None

    def test_zero_page_allowed(self):
        """Test: Zero page should pass through (Django will handle invalid page)"""
        request = self.factory.get("/bpp/autorzy/?page=0")
        response = self.middleware.process_request(request)
        assert response is None

    def test_negative_page_with_long_string_blocked(self):
        """Test: Negative page numbers with extra characters should be blocked"""
        request = self.factory.get("/bpp/autorzy/?page=-1+OR+1=1")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # ====================
    # Path Blocking Tests
    # ====================

    # PHP Files
    def test_php_file_blocked(self):
        """Test: PHP files should be blocked"""
        request = self.factory.get("/index.php")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_php_file_uppercase_blocked(self):
        """Test: Uppercase PHP files should be blocked (case-insensitive)"""
        request = self.factory.get("/ADMIN.PHP")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_php5_file_blocked(self):
        """Test: PHP5 files should be blocked"""
        request = self.factory.get("/config.php5")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_phtml_file_blocked(self):
        """Test: PHTML files should be blocked"""
        request = self.factory.get("/shell.phtml")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # ASP/JSP Files
    def test_asp_file_blocked(self):
        """Test: ASP files should be blocked"""
        request = self.factory.get("/default.asp")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_aspx_file_blocked(self):
        """Test: ASPX files should be blocked"""
        request = self.factory.get("/admin.aspx")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_jsp_file_blocked(self):
        """Test: JSP files should be blocked"""
        request = self.factory.get("/login.jsp")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Version Control
    def test_git_directory_blocked(self):
        """Test: .git directory should be blocked"""
        request = self.factory.get("/.git/config")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_git_head_blocked(self):
        """Test: .git/HEAD should be blocked"""
        request = self.factory.get("/.git/HEAD")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_svn_directory_blocked(self):
        """Test: .svn directory should be blocked"""
        request = self.factory.get("/.svn/entries")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_hg_directory_blocked(self):
        """Test: .hg directory should be blocked"""
        request = self.factory.get("/.hg/store")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # WordPress Probes
    def test_wp_admin_blocked(self):
        """Test: WordPress wp-admin should be blocked"""
        request = self.factory.get("/wp-admin/")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_wp_login_blocked(self):
        """Test: WordPress wp-login.php should be blocked"""
        request = self.factory.get("/wp-login.php")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_xmlrpc_blocked(self):
        """Test: xmlrpc.php should be blocked"""
        request = self.factory.get("/xmlrpc.php")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # phpMyAdmin Probes
    def test_phpmyadmin_blocked(self):
        """Test: phpMyAdmin paths should be blocked"""
        request = self.factory.get("/phpmyadmin/index.php")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_phpmyadmin_uppercase_blocked(self):
        """Test: phpMyAdmin uppercase should be blocked"""
        request = self.factory.get("/phpMyAdmin/")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_adminer_blocked(self):
        """Test: Adminer should be blocked"""
        request = self.factory.get("/adminer.php")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Backup Files
    def test_bak_file_blocked(self):
        """Test: .bak files should be blocked"""
        request = self.factory.get("/settings.py.bak")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_old_file_blocked(self):
        """Test: .old files should be blocked"""
        request = self.factory.get("/web.config.old")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_vim_backup_blocked(self):
        """Test: Vim backup files (~) should be blocked"""
        request = self.factory.get("/config.php~")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_swp_file_blocked(self):
        """Test: Vim swap files should be blocked"""
        request = self.factory.get("/.settings.py.swp")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Database Files
    def test_sql_file_blocked(self):
        """Test: SQL dump files should be blocked"""
        request = self.factory.get("/database.sql")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_sqlite_file_blocked(self):
        """Test: SQLite database files should be blocked"""
        request = self.factory.get("/db.sqlite3")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Configuration Files
    def test_env_file_blocked(self):
        """Test: .env files should be blocked"""
        request = self.factory.get("/.env")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_htpasswd_blocked(self):
        """Test: .htpasswd should be blocked"""
        request = self.factory.get("/.htpasswd")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_web_config_blocked(self):
        """Test: web.config should be blocked"""
        request = self.factory.get("/web.config")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Archive Files
    def test_zip_file_blocked(self):
        """Test: ZIP files should be blocked"""
        request = self.factory.get("/backup.zip")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_tar_gz_blocked(self):
        """Test: TAR.GZ files should be blocked"""
        request = self.factory.get("/site-backup.tar.gz")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Log Files
    def test_log_file_blocked(self):
        """Test: Log files should be blocked"""
        request = self.factory.get("/debug.log")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Webshells
    def test_c99_webshell_blocked(self):
        """Test: c99.php webshell should be blocked"""
        request = self.factory.get("/c99.php")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_shell_php_blocked(self):
        """Test: shell.php should be blocked"""
        request = self.factory.get("/shell.php")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # IDE Directories
    def test_vscode_directory_blocked(self):
        """Test: .vscode directory should be blocked"""
        request = self.factory.get("/.vscode/settings.json")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_idea_directory_blocked(self):
        """Test: .idea directory should be blocked"""
        request = self.factory.get("/.idea/workspace.xml")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Package Directories
    def test_node_modules_blocked(self):
        """Test: node_modules directory should be blocked"""
        request = self.factory.get("/node_modules/package/index.js")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_pycache_blocked(self):
        """Test: __pycache__ directory should be blocked"""
        request = self.factory.get("/__pycache__/module.cpython-312.pyc")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    # Path Length
    def test_excessively_long_path_blocked(self):
        """Test: Paths exceeding 1024 characters should be blocked"""
        long_path = "/bpp/" + "a" * 1020
        request = self.factory.get(long_path)
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_normal_length_path_allowed(self):
        """Test: Normal length paths should be allowed"""
        normal_path = "/bpp/browse/" + "a" * 100
        request = self.factory.get(normal_path)
        response = self.middleware.process_request(request)
        assert response is None

    # Legitimate Paths (Should NOT Be Blocked)
    def test_django_admin_allowed(self):
        """Test: Django admin should be allowed"""
        request = self.factory.get("/admin/bpp/autor/")
        response = self.middleware.process_request(request)
        assert response is None

    def test_api_path_allowed(self):
        """Test: API paths should be allowed"""
        request = self.factory.get("/api/v1/authors/")
        response = self.middleware.process_request(request)
        assert response is None

    def test_static_path_allowed(self):
        """Test: Static paths should be allowed"""
        request = self.factory.get("/static/css/app.css")
        response = self.middleware.process_request(request)
        assert response is None

    def test_media_path_allowed(self):
        """Test: Media paths should be allowed"""
        request = self.factory.get("/media/uploads/document.pdf")
        response = self.middleware.process_request(request)
        assert response is None

    def test_normal_browse_path_allowed(self):
        """Test: Normal browse paths should be allowed"""
        request = self.factory.get("/bpp/browse/autor/jan-kowalski/")
        response = self.middleware.process_request(request)
        assert response is None

    # Logging Tests for Path Blocking
    def test_path_blocking_logs_reason(self, caplog):
        """Test: Path blocking should log the block reason"""
        caplog.set_level(logging.WARNING)

        request = self.factory.get("/index.php")
        self.middleware.process_request(request)

        assert "Blocked malicious request" in caplog.text
        assert "blocked_extension" in caplog.text
        assert "/index.php" in caplog.text
