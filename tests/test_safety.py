from circuit_agent.safety import check_scope
def test_scope_rejects_mains_before_design(): assert not check_scope("design a 230 VAC mains controller",{}).allowed
def test_scope_pauses_ambiguous_supply(): assert check_scope("design a power supply",{}).classification == "needs_clarification"
