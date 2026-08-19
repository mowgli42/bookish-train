Feature: Package progress updates
  As an edge engine
  I want to PATCH package progress and status during transfer
  So the signal board can show live upload state and resume work

  Background:
    Given the Catcher API is available at CATCHER_URL
    And a package exists from POST /api/v1/ingest for source_id "engine-progress"

  Scenario: Report in-progress transfer
    When I PATCH /api/v1/packages/{package_id} with:
      | status      | progress_percent |
      | in_progress | 55               |
    Then the response status is 200
    And the package progress_percent is 55
    And the package status is "in_progress"
    When I GET /api/v1/packages/{package_id}
    Then the package status is "in_progress"
    And the package progress_percent is 55

  Scenario: Complete a transfer
    When I PATCH /api/v1/packages/{package_id} with:
      | status    | progress_percent |
      | completed | 100              |
    Then the response status is 200
    And the package status is "completed"
    And the package progress_percent is 100

  Scenario: Failed transfer appears on resume switch list
    When I PATCH /api/v1/packages/{package_id} with:
      | status | progress_percent | last_error           |
      | failed | 40               | scenario retry check |
    Then the response status is 200
    When I GET /api/v1/sources/engine-progress/resume
    Then the response status is 200
    And resume.count is greater than or equal to 1
    And the switch_list includes the package with status "failed"

  Scenario: Jobs alias accepts the same PATCH body
    When I PATCH /api/v1/jobs/{package_id} with:
      | status      | progress_percent |
      | in_progress | 10               |
    Then the response status is 200
    And the package progress_percent is 10
