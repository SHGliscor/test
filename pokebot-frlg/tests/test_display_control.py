from pokebot_frlg.wifi_botbase import WiFiBotbase


def test_koi_display_commands():
    bot=WiFiBotbase("127.0.0.1")
    sent=[]
    bot.send=sent.append
    bot.screen_off(); bot.screen_on()
    assert sent == ["screenOff", "screenOn"]

if __name__ == "__main__":
    test_koi_display_commands(); print("PASS display control commands")
