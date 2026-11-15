# TASK-1302: Group-scoped tests, attributes, and user-defined connectors

Depends on: TASK-1301

Once users can organize files into custom groups (`TASK-1301`), downstream configuration should support targeting a group as a first-class unit rather than repeating settings per file.

- Allow output test suites (`01-output-testing`: `DocumentAssertionSuite`, `RetrievalTestSuite`) to be attached to a file group so all member documents inherit and run those assertions.
- Allow pipeline and quality attributes (such as `language`, `taxonomy`, `target_threshold`, preset overrides, and postprocessing rules) to be defined at the group level and inherited by member files unless explicitly overridden per file.
- Design the connector configuration contract (`03-downstream-piping` and future user-defined connectors) so connectors can subscribe to a group (e.g. forwarding all accepted runs from a group to a webhook, watched folder, or external knowledge base) instead of individual files.
- Update the Web Hub Planning and Results UI to display inherited group attributes, group-level test status, and group-scoped connector bindings.

Add unit tests in `src/tests/test_group_scoped_config.py`.
