-- SynoStream localized MPV context menu.
-- Copyright (C) 2026 Lőrincz László
-- SPDX-License-Identifier: GPL-3.0-only

local language = os.getenv("SYNOSTREAM_MPV_LANGUAGE") or "hu"
local english = language == "en"

local labels = english and {
    play = "Play",
    pause = "Pause",
    audio = "Audio track",
    subtitle = "Subtitles",
    no_audio = "No audio track",
    no_subtitle = "No subtitles",
    audio_track = "Audio track",
    subtitle_track = "Subtitle track",
    volume_down = "Decrease volume",
    volume_up = "Increase volume",
    seek_back = "Back 10 seconds",
    seek_forward = "Forward 10 seconds",
    fullscreen = "Fullscreen",
    no_tracks = "No tracks available",
} or {
    play = "Lejátszás",
    pause = "Szünet",
    audio = "Hangsáv",
    subtitle = "Felirat",
    no_audio = "Nincs hangsáv",
    no_subtitle = "Felirat kikapcsolása",
    audio_track = "Hangsáv",
    subtitle_track = "Felirat",
    volume_down = "Hangerő csökkentése",
    volume_up = "Hangerő növelése",
    seek_back = "Vissza 10 másodpercet",
    seek_forward = "Előre 10 másodpercet",
    fullscreen = "Teljes képernyő",
    no_tracks = "Nincs elérhető sáv",
}

local function track_title(track, kind, index)
    local title = track.title
    if not title or title == "" then
        title = track.lang
    end
    if not title or title == "" then
        title = labels[kind .. "_track"] .. " " .. tostring(index)
    elseif track.lang and track.lang ~= "" and track.lang ~= title then
        title = title .. " (" .. track.lang .. ")"
    end
    return title
end

local function track_menu(kind, property, off_title)
    local items = {}
    local tracks = mp.get_property_native("track-list") or {}
    local selected = 0

    if kind == "sub" then
        items[#items + 1] = {
            title = off_title,
            cmd = "set sid no",
            state = mp.get_property("sid") == "no" and {"checked"} or {},
        }
    end

    for _, track in ipairs(tracks) do
        if track.type == kind and not track.image then
            local id = tonumber(track.id)
            if id then
                selected = selected + 1
                items[#items + 1] = {
                    title = track_title(track, kind == "audio" and "audio" or "subtitle", selected),
                    cmd = "set " .. property .. " " .. tostring(id),
                    state = track.selected and {"checked"} or {},
                }
            end
        end
    end

    if #items == 0 then
        items[1] = {title = off_title or labels.no_tracks, state = {"disabled"}}
    end
    return items
end

local function update_menu()
    local paused = mp.get_property_native("pause")
    local fullscreen = mp.get_property_native("fullscreen")
    local subtitles_visible = mp.get_property_native("sub-visibility")

    mp.set_property_native("menu-data", {
        {title = paused and labels.play or labels.pause, cmd = "cycle pause"},
        {type = "separator"},
        {title = labels.audio, type = "submenu", submenu = track_menu("audio", "aid", labels.no_audio)},
        {title = labels.subtitle, type = "submenu", submenu = track_menu("sub", "sid", labels.no_subtitle)},
        {title = english and "Show subtitles" or "Feliratok megjelenítése",
         cmd = "cycle sub-visibility", state = subtitles_visible and {"checked"} or {}},
        {type = "separator"},
        {title = labels.volume_down, cmd = "add volume -5"},
        {title = labels.volume_up, cmd = "add volume 5"},
        {title = labels.seek_back, cmd = "seek -10"},
        {title = labels.seek_forward, cmd = "seek 10"},
        {type = "separator"},
        {title = labels.fullscreen, cmd = "cycle fullscreen", state = fullscreen and {"checked"} or {}},
    })
end

mp.observe_property("track-list", "native", update_menu)
mp.observe_property("pause", "bool", update_menu)
mp.observe_property("fullscreen", "bool", update_menu)
mp.observe_property("sub-visibility", "bool", update_menu)
mp.register_event("file-loaded", update_menu)
mp.add_key_binding("MBTN_RIGHT", "synostream-context-menu", function()
    mp.commandv("script-message-to", "context_menu", "open")
end)

update_menu()
