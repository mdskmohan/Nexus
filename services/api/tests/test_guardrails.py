from nexus.guardrails.citations import verify_quote
from nexus.guardrails.scan import scan
from nexus.samples import INJECTION_EMAIL

PASSAGE = (
    "3.2 The Receiving Party may disclose Confidential Information to its employees, officers and "
    "professional advisers who need to know it for the Purpose and who are bound by obligations of "
    "confidentiality no less protective than those in this Agreement."
)


class TestCitations:
    def test_exact_quote_is_verified(self):
        assert verify_quote("professional advisers who need to know it", PASSAGE).ok

    def test_case_whitespace_and_typography_are_ignored(self):
        quote = "THE Receiving   Party\nmay disclose “Confidential Information”".replace("“", "").replace("”", "")
        assert verify_quote(quote, PASSAGE).ok
        assert verify_quote("no less protective than those in this Agreement", PASSAGE.replace(" ", "  ")).ok

    def test_curly_and_straight_quotes_match(self):
        assert verify_quote("the “Purpose”", 'defined as the "Purpose" below').ok

    def test_ellipsis_fragments_must_appear_in_order(self):
        assert verify_quote("may disclose Confidential Information … bound by obligations", PASSAGE).ok
        assert verify_quote("may disclose ... bound by obligations of confidentiality", PASSAGE).ok
        assert not verify_quote("bound by obligations … may disclose Confidential Information", PASSAGE).ok

    def test_altered_wording_fails(self):
        check = verify_quote("may disclose Confidential Information to any third party", PASSAGE)
        assert not check.ok
        assert "do not appear" in check.reason

    def test_trivially_short_quotes_fail(self):
        assert not verify_quote("the", PASSAGE).ok
        assert not verify_quote("", PASSAGE).ok


class TestScan:
    def test_planted_instruction_is_flagged(self):
        result = scan([(0, 1, INJECTION_EMAIL)])
        assert len(result.hidden_instructions) == 1
        assert "ignore its instructions" in result.hidden_instructions[0]["why"]

    def test_ordinary_contract_text_is_not_flagged(self):
        result = scan([(0, 1, PASSAGE), (1, 1, "The Supplier shall respond within five (5) Business Days.")])
        assert result.hidden_instructions == []
        assert result.sensitive == {}

    def test_sensitive_numbers(self):
        text = "SSN 123-45-6789. Card 4111 1111 1111 1111. PAN ABCPE1234F. Not a card: 1234 5678 9012 3456."
        result = scan([(0, 1, text)])
        assert result.sensitive["US social security number"] == 1
        assert result.sensitive["payment card number"] == 1
        assert result.sensitive["Indian PAN"] == 1
