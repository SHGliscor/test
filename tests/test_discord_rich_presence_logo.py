from pokebot_frlg.rich_presence_assets import RPC_LARGE_IMAGE, RPC_LARGE_TEXT


def test_frlg_rich_presence_uses_game_logo_asset_key():
    assert RPC_LARGE_IMAGE == "frlg-logo"
    assert "FireRed" in RPC_LARGE_TEXT and "LeafGreen" in RPC_LARGE_TEXT
