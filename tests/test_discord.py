from pokebot_frlg.discord_payloads import build_embed_payload


def test_shiny_embed_contains_frlg_details():
    embed,image=build_embed_payload("shiny",{
        "name":"Charmander","game":"LeafGreen","hunt":"Charmander — Starter","attempt":42,
        "nature":"Jolly","ability_name":"Blaze","shiny_xor":3,"iv_spread":"31/30/29/28/27/26",
        "pid":0x1234ABCD,"session_encounters":42,"session_shinies":1,"lifetime_encounters":500,
        "lifetime_shinies":8,"sprite_path":"x.png"
    })
    assert "Shiny Charmander" in embed["title"]
    text=" ".join(str(f["value"]) for f in embed["fields"])
    assert "Blaze" in text and "31/30/29/28/27/26" in text and "1234ABCD" in text
    assert image=="x.png"


def test_status_is_monitoring_only():
    embed,_=build_embed_payload("status",{"connected":True,"game":"FireRed","hunt":"Mewtwo","session_encounters":10,"session_shinies":0,"lifetime_encounters":100,"lifetime_shinies":1})
    assert "monitoring only" in embed["footer"]["text"].lower()
