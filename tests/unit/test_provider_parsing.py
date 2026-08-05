from xml.etree import ElementTree

from gbb_terminal.market_data.providers.sec import SECProvider


def test_sec_field_reads_direct_and_nested_values():
    root = ElementTree.fromstring("""
        <ownershipDocument>
          <issuer><issuerName>Example Corp</issuerName></issuer>
          <transaction>
            <transactionShares><value>1250</value></transactionShares>
          </transaction>
        </ownershipDocument>
    """)
    assert SECProvider._field(root, "issuerName") == "Example Corp"
    assert SECProvider._field(root, "transactionShares") == "1250"
    assert SECProvider._field(root, "missing") is None


def test_sec_number_handles_missing_and_invalid_values():
    assert SECProvider._number("12.5") == 12.5
    assert SECProvider._number(None) is None
    assert SECProvider._number("not-a-number") is None
