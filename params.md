# Parameters Alignment Report

Scope: `agents/` vs tool definitions in `tools/`. For each agent, parameters used in code were compared to parameters declared in the corresponding tool JSON. Items are reported as:
- Missing in tool: agent reads a parameter not declared in tool JSON.
- Unused in agent: tool JSON declares a parameter not read by the agent.

## customer_segmentation_agent.py
- Tool: tools/customer_segmentation_tool.json (agent: customer-segmentation-agent)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## experimental_design_agent.py
- Tool: tools/experimental_design_tool.json (agent: experimental-design-agent)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## market_basket_sequence_agent.py
- Tool: tools/market_basket_sequence_tool.json (agent: market-basket-sequence-agent)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## synthetic_control_agent.py
- Tool: tools/synthetic_control_tool.json (agent: synthetic-control-agent)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## unified_profiler.py
- Tool: tools/profile_my_data_tool.json (agent: unified-profiler)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## drift_detector.py
- Tool: tools/profile_my_data_tool.json (agent: drift-detector)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## score_risk.py
- Tool: tools/profile_my_data_tool.json (agent: score-risk)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## test_coverage_agent.py
- Tool: tools/profile_my_data_tool.json (agent: test-coverage-agent)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## readiness_rater.py
- Tool: tools/profile_my_data_tool.json (agent: readiness-rater)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## key_identifier.py
- Tool: tools/master_my_data_tool.json (agent: key-identifier)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## contract_enforcer.py
- Tool: tools/master_my_data_tool.json (agent: contract-enforcer)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## semantic_mapper.py
- Tool: tools/master_my_data_tool.json (agent: semantic-mapper)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## survivorship_resolver.py
- Tool: tools/master_my_data_tool.json (agent: survivorship-resolver)
- Missing in tool: quality_score_columns
- Unused in agent: None
- Verdict: Issues found

## golden_record_builder.py
- Tool: tools/master_my_data_tool.json (agent: golden-record-builder)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## stewardship_flagger.py
- Tool: tools/master_my_data_tool.json (agent: stewardship-flagger)
- Missing in tool: confidence_columns
- Unused in agent: None
- Verdict: Issues found

## cleanse_previewer.py
- Tool: tools/clean_my_data_tool.json (agent: cleanse-previewer)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## quarantine_agent.py
- Tool: tools/clean_my_data_tool.json (agent: quarantine-agent)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## type_fixer.py
- Tool: tools/clean_my_data_tool.json (agent: type-fixer)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## field_standardization.py
- Tool: tools/clean_my_data_tool.json (agent: field-standardization)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## duplicate_resolver.py
- Tool: tools/clean_my_data_tool.json (agent: duplicate-resolver)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## null_handler.py
- Tool: tools/clean_my_data_tool.json (agent: null-handler)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## outlier_remover.py
- Tool: tools/clean_my_data_tool.json (agent: outlier-remover)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## cleanse_writeback.py
- Tool: tools/clean_my_data_tool.json (agent: cleanse-writeback)
- Missing in tool: None
- Unused in agent: None
- Verdict: OK

## lineage_tracer.py
- Tool: No matching tool definition found
- Missing in tool: N/A
- Unused in agent: N/A
- Verdict: No tool mapping

## governance_checker.py
- Tool: No matching tool definition found
- Missing in tool: N/A
- Unused in agent: N/A
- Verdict: No tool mapping

## master_writeback_agent.py
- Tool: No matching tool definition found
- Missing in tool: N/A
- Unused in agent: N/A
- Verdict: No tool mapping
