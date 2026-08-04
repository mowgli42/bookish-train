Feature: Package ingest
  As an edge engine
  I want to POST package manifests to the Catcher dispatcher
  So that railcars are tracked without uploading payload bytes

  Background:
    Given the Catcher API is available at CATCHER_URL
    And demo state may be reset via POST /api/v1/demo/reset

  Scenario: Ingest a package and list it
    When I POST /api/v1/ingest with:
      | source_id  | path              | checksum                                                         | size_bytes |
      | engine-a   | data/sample.txt   | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | 0          |
    Then the response status is 200
    And the response JSON includes package_id (alias job_id)
    When I GET /api/v1/packages
    Then the response status is 200
    And the packages list includes path "data/sample.txt" for source_id "engine-a"
    And that package has status "pending" and progress_percent 0

  Scenario: Ingest rejects size_bytes > 0 without checksum
    When I POST /api/v1/ingest with:
      | source_id | path | size_bytes |
      | engine-a  | x    | 1          |
    Then the response status is 422

  Scenario: Register source then ingest under that source
    When I POST /api/v1/sources with:
      | source_id | label          |
      | engine-b  | Scenario engine |
    And I POST /api/v1/ingest with:
      | source_id | path           | checksum                                                         | size_bytes |
      | engine-b  | report.json    | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | 0          |
    When I GET /api/v1/sources
    Then the sources list includes source_id "engine-b"
    When I GET /api/v1/packages?source_id=engine-b
    Then every returned package has source_id "engine-b"

  @wip @phase2
  Scenario: Windows endpoint agent ingests to Catcher
    # Phase 2 — Windows agent not implemented as a first-class client yet
    Given a Windows endpoint agent is configured
    When the agent completes a backup package
    Then the Catcher receives POST /api/v1/ingest for that package
