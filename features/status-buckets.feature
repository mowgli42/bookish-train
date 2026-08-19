Feature: Status and bucket summaries
  As a signal-board consumer
  I want to read component status and bucket summaries
  So I can monitor the railway without inspecting storage stations

  Background:
    Given the Catcher API is available at CATCHER_URL

  Scenario: Health endpoint reports ok
    When I GET /health
    Then the response status is 200
    And the response JSON has status "ok"

  Scenario: Status returns catcher and bucket component fields
    When I GET /api/v1/status
    Then the response status is 200
    And components.catcher.status is "ok"
    And components.buckets includes keys hot, warm, cold, offsite
    And components.client.status is "active" or "idle"

  Scenario: Buckets summary lists tiers
    When I GET /api/v1/buckets
    Then the response status is 200
    And the response JSON has a buckets array
    And each bucket entry has name, count, and total_bytes

  Scenario: Ingest updates bucket counts visible via status
    Given demo state is reset via POST /api/v1/demo/reset
    When I POST /api/v1/ingest with a valid zero-byte package for source_id "engine-status"
    And I GET /api/v1/status
    Then components.catcher.jobs_count is greater than or equal to 1
    When I GET /api/v1/buckets
    Then the sum of bucket counts is greater than or equal to 1

  Scenario: Config and projections are readable for the dashboard
    When I GET /api/v1/config
    Then the response status is 200
    And rule_sets or retention is present
    When I GET /api/v1/projections?days=5
    Then the response status is 200
    And transitions is an array

  @wip @phase4
  Scenario: Tier transitions reflect retention after aging
    # Phase 4 — storage tier transitions / rclone-restic validation
    Given packages have aged past hot wait in retention rules
    When I GET /api/v1/buckets
    Then package bucket assignments reflect warm or colder tiers
