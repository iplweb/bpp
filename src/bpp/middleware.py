import json
import logging

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from rollbar.contrib.django.middleware import RollbarNotifierMiddleware

logger = logging.getLogger("django.request")


class MaliciousRequestBlockingMiddleware(MiddlewareMixin):
    """
    Middleware to block malicious requests including:
    - SQL injection attempts in pagination parameters
    - Requests for PHP, ASP, JSP files (not used in Django)
    - Version control directories (.git, .svn, etc.)
    - Backup and temporary files
    - Configuration files (.env, .htpasswd, etc.)
    - Database dumps and log files
    - Common CMS admin panel probes (WordPress, phpMyAdmin, etc.)
    - Paths exceeding 1024 characters
    - Full URLs (path + query string) exceeding 2048 characters
    - Nested ``?next=`` redirect chains produced by scanner bots

    Returns HTTP 444 (No Response) for blocked requests.
    """

    # Maximum length of the full request URL (path + query string).
    # Path alone is capped at 1024 (see process_request); the query string can
    # legitimately carry a single ``next=`` redirect, so we allow more headroom.
    MAX_FULL_PATH_LENGTH = 2048

    # Blocked file extensions (case-insensitive)
    BLOCKED_EXTENSIONS = (
        # Script files (not used in Django)
        ".php",
        ".php3",
        ".php4",
        ".php5",
        ".phtml",
        ".asp",
        ".aspx",
        ".asmx",
        ".jsp",
        ".jspx",
        ".cgi",
        ".pl",
        # Backup files
        ".bak",
        ".backup",
        ".old",
        ".orig",
        ".copy",
        ".tmp",
        ".temp",
        ".save",
        ".swp",
        ".swo",
        # Database files
        ".sql",
        ".dump",
        ".pgdump",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".mdb",
        # Configuration files
        ".env",
        ".htaccess",
        ".htpasswd",
        ".ini",
        ".conf",
        # Archive files
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".rar",
        ".7z",
        # Log files
        ".log",
        ".out",
        ".err",
    )

    # Blocked path patterns (case-insensitive)
    BLOCKED_PATHS = (
        # Version control directories
        "/.git/",
        "/.svn/",
        "/.hg/",
        "/.bzr/",
        # CMS admin paths
        "/wp-admin/",
        "/wp-login.php",
        "/wp-content/",
        "/wp-includes/",
        "/administrator/",
        "/phpmyadmin/",
        "/phpMyAdmin/",
        "/pma/",
        "/PMA/",
        "/adminer/",
        "/adminer.php",
        "/webadmin/",
        "/cpanel/",
        # Common probes
        "/config.php",
        "/configuration.php",
        "/settings.php",
        "/setup.php",
        "/install.php",
        "/install/",
        "/xmlrpc.php",
        # Webshells
        "/shell.php",
        "/c99.php",
        "/r57.php",
        # IDE directories
        "/.vscode/",
        "/.idea/",
        "/.vs/",
        # Package directories
        "/node_modules/",
        "/__pycache__/",
        "/.pytest_cache/",
        # Config file patterns
        "/web.config",
        "/Web.config",
    )

    # Blocked path suffixes (for vim backups like file.py~)
    BLOCKED_SUFFIXES = ("~",)

    def process_request(self, request):  # noqa: C901
        path = request.path
        path_lower = path.lower()

        # Block excessively long paths (potential buffer overflow attempts)
        if len(path) > 1024:
            return self._block_request(request, "path_too_long", path[:100])

        # Block excessively long full URLs (path + query string). Catches
        # scanner bots that follow login redirects without cookies and end up
        # accumulating exponentially growing percent-encoded ``?next=`` chains.
        full_path = request.get_full_path()
        if len(full_path) > self.MAX_FULL_PATH_LENGTH:
            return self._block_request(request, "url_too_long", full_path[:100])

        # Block nested ``?next=`` redirect chains. Django decodes one level of
        # percent-encoding when parsing query string, so a legitimate single
        # redirect target (e.g. ``next=/foo/``) never contains ``?next=`` —
        # but a re-redirected scanner trail does (``next=/login/?next=/foo``).
        next_param = request.GET.get("next", "")
        if next_param and "?next=" in next_param.lower():
            return self._block_request(request, "nested_next", next_param[:100])

        # Check pagination parameter for SQL injection
        page_param = request.GET.get("page", "")
        if page_param:
            # Allow "last" keyword (Django pagination feature)
            if page_param.lower() != "last":
                # Block if > 5 chars AND contains non-numeric characters
                if len(page_param) > 5 and not page_param.isdigit():
                    return self._block_request(request, "pagination", page_param[:100])

        # Check for blocked file extensions
        for ext in self.BLOCKED_EXTENSIONS:
            if path_lower.endswith(ext):
                return self._block_request(request, "blocked_extension", path[:100])

        # Check for blocked path patterns
        for blocked_path in self.BLOCKED_PATHS:
            if blocked_path.lower() in path_lower:
                return self._block_request(request, "blocked_path", path[:100])

        # Check for vim backup files (ending with ~)
        for suffix in self.BLOCKED_SUFFIXES:
            if path.endswith(suffix):
                return self._block_request(request, "backup_file", path[:100])

        return None

    def _block_request(self, request, block_reason, identifier):
        """Block a malicious request and log the attempt."""
        logger.warning(
            "Blocked malicious request [%s]: %s",
            block_reason,
            identifier,
            extra={
                "status_code": 444,
                "request": request,
                "remote_addr": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
                "block_reason": block_reason,
            },
        )
        # HTTP 444 - No Response (nginx convention for blocking malicious requests)
        return HttpResponse("", status=444)


# Backward compatibility alias
PageParameterValidationMiddleware = MaliciousRequestBlockingMiddleware


class NonHtmlDebugToolbarMiddleware(MiddlewareMixin):
    """
    The Django Debug Toolbar usually only works for views that return HTML.
    This middleware wraps any non-HTML response in HTML if the request
    has a 'debug' query parameter (e.g. http://localhost/foo?debug)
    Special handling for json (pretty printing) and
    binary data (only show data length)
    """

    @staticmethod
    def process_response(request, response):
        debug = request.GET.get("debug", "UNSET")

        if debug != "UNSET":
            if response["Content-Type"] == "application/octet-stream":
                new_content = (
                    "<html><body>Binary Data, "
                    f"Length: {len(response.content)}</body></html>"
                )
                response = HttpResponse(new_content)
            elif response["Content-Type"] != "text/html":
                content = response.content
                try:
                    json_ = json.loads(content)
                    content = json.dumps(json_, sort_keys=True, indent=2)
                except ValueError:
                    pass
                response = HttpResponse(
                    f"<html><body><pre>{content}</pre></body></html>"
                )

        return response


class CustomRollbarNotifierMiddleware(RollbarNotifierMiddleware):
    def get_extra_data(self, request, exc):
        from django.conf import settings

        return {
            "DJANGO_BPP_HOSTNAME": settings.DJANGO_BPP_HOSTNAME,
        }

    def get_payload_data(self, request, exc):
        payload_data = dict()

        if not request.user.is_anonymous:
            # Adding info about the user affected by this event (optional)
            # The 'id' field is required, anything else is optional
            payload_data = {
                "person": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "email": request.user.email,
                },
            }

        return payload_data
