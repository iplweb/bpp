Zastąpienie systemu śledzenia błędów Sentry SDK na Rollbar. Wszystkie wywołania ``capture_exception`` z modułu ``sentry_sdk`` zostały zamienione na ``rollbar.report_exc_info(sys.exc_info())``.
