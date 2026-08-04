Feature: Text UI live monitoring
  As an operator on SSH or a headless host
  I want a terminal signal board backed by the same Catcher APIs
  So I can monitor status without a browser

  Background:
    Given the Catcher API is available at CATCHER_URL
    And scripts/text-ui.py is the text UI entrypoint

  Scenario: One-shot report reads status and buckets
    When I run `python scripts/text-ui.py` (default one-shot)
    Then the process exits successfully
    And the report is built from GET /api/v1/status
    And the report is built from GET /api/v1/buckets
    And the report is built from GET /api/v1/packages

  Scenario: Live refresh mode is available
    When I run `python scripts/text-ui.py --live --refresh 5`
    Then the UI periodically re-fetches status, buckets, and packages
    And refresh interval is 5 seconds

  Scenario: AI format emits EBK status lines
    When I run `python scripts/text-ui.py --format ai`
    Then output includes tab-separated EBK status lines derived from /api/v1/status and /api/v1/packages

  Scenario: JSON format emits a machine-readable summary
    When I run `python scripts/text-ui.py --format json`
    Then output is a JSON document with status, buckets, and packages keys
