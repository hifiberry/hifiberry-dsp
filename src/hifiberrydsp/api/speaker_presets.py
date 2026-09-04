'''
Speaker presets: discovery, validation and compatibility.

A speaker preset is a small JSON document describing one loudspeaker as four
DSP channels -- a biquad bank, a role, a level, a delay and a polarity each.
Applying one turns a bare four-channel amplifier into an active crossover for
that speaker.

Everything here is pure: no DSP, no Flask. The rules that decide whether a
preset may be applied, and what would be written if it were, are testable
without hardware.

Copyright (c) 2026 Modul 9/HiFiBerry
'''

import json
import logging
import os

# Overridable for tests.
SYSTEM_DIR = "/usr/share/hifiberry/speaker-presets"
USER_DIR = "/var/lib/hifiberry/speaker-presets"

SCHEMA_VERSION = 2
CHANNELS = ("a", "b", "c", "d")
COEFFICIENTS = ("a0", "a1", "a2", "b0", "b1", "b2")

# What an unused bank slot holds: [0, 0, 1, 0, 0] in DSP words.
TRANSPARENT = {"a0": 1.0, "a1": 0.0, "a2": 0.0,
               "b0": 1.0, "b1": 0.0, "b2": 0.0}

# Used only when a profile's channelSelect register carries no 'channels'
# attribute. Profiles written before that attribute existed used this order.
ROLE_FALLBACK = ("left", "right", "mono", "side")


class PresetError(Exception):
    '''Base class for preset problems.'''


class PresetNotFound(PresetError):
    '''No preset with that id in either directory.'''


class PresetInvalid(PresetError):
    '''The preset is malformed, or cannot be expressed on this profile.'''


def preset_dirs():
    '''
    The directories to search, lowest priority first, as (path, read_only).

    Read from the module globals on every call so tests can redirect them.
    '''
    return ((SYSTEM_DIR, True), (USER_DIR, False))


def validate(preset, preset_id):
    '''
    Check a preset document, raising PresetInvalid on the first problem.

    Args:
        preset (dict): The parsed document
        preset_id (str): The id the filename implies

    Raises:
        PresetInvalid: with a message naming what is wrong
    '''
    if not isinstance(preset, dict):
        raise PresetInvalid("Preset is not a JSON object")

    version = preset.get("schemaVersion")
    if version != SCHEMA_VERSION:
        raise PresetInvalid(
            f"Unsupported schemaVersion {version!r}, expected {SCHEMA_VERSION}")

    # The id decides which preset an apply request reaches. A file whose id
    # disagrees with its name would be reachable under one and act as the
    # other, so this is an error rather than a preference for either.
    if preset.get("id") != preset_id:
        raise PresetInvalid(
            f"id {preset.get('id')!r} does not match filename {preset_id!r}")

    for field in ("name", "requiredProfile"):
        if not preset.get(field):
            raise PresetInvalid(f"Missing required field {field!r}")

    for field in ("minProfileVersion", "sampleRate"):
        if not isinstance(preset.get(field), int):
            raise PresetInvalid(f"{field!r} must be an integer")

    channels = preset.get("channels")
    if not isinstance(channels, dict):
        raise PresetInvalid("Missing 'channels' object")

    for channel in CHANNELS:
        settings = channels.get(channel)
        if not isinstance(settings, dict):
            raise PresetInvalid(f"Missing settings for channel {channel!r}")
        if not settings.get("role"):
            raise PresetInvalid(f"Channel {channel!r} has no role")

        # These fields are optional -- channel_register_writes() already
        # defaults them, and other-speaker.json genuinely omits some -- but
        # when present they must be usable, or a hand-edited user preset
        # would pass here and only blow up with a bare ValueError the first
        # time something applies it.
        for field in ("level", "delayMs"):
            value = settings.get(field)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise PresetInvalid(
                        f"Channel {channel!r} {field!r} must be a number")
                if value < 0:
                    raise PresetInvalid(
                        f"Channel {channel!r} {field!r} must not be negative")

        for field in ("invert", "enabled"):
            value = settings.get(field)
            if value is not None and not isinstance(value, bool):
                raise PresetInvalid(
                    f"Channel {channel!r} {field!r} must be a boolean")

        if not isinstance(settings.get("filters"), list):
            raise PresetInvalid(f"Channel {channel!r} has no filter list")
        for index, filter_data in enumerate(settings["filters"]):
            missing = [c for c in COEFFICIENTS if c not in filter_data]
            if missing:
                raise PresetInvalid(
                    f"Channel {channel!r} filter {index} is missing "
                    f"{', '.join(missing)}")


def load_preset_file(path, preset_id):
    '''Read and validate one preset file.'''
    try:
        with open(path) as handle:
            preset = json.load(handle)
    except (IOError, ValueError) as e:
        raise PresetInvalid(f"Could not read {path}: {e}")

    validate(preset, preset_id)
    return preset


def list_presets():
    '''
    Every readable preset, as {id: (preset, read_only)}.

    A user preset shadows a system preset of the same id. One malformed file
    is logged and skipped rather than taken as a failure of the whole list --
    a hand-edited file in the user directory must not hide the bundled ones.
    '''
    found = {}
    for directory, read_only in preset_dirs():
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json"):
                continue
            preset_id = name[:-len(".json")]
            path = os.path.join(directory, name)
            try:
                found[preset_id] = (load_preset_file(path, preset_id),
                                    read_only)
            except PresetInvalid as e:
                logging.warning("Ignoring speaker preset %s: %s", path, e)
    return found


def get_preset(preset_id):
    '''
    One preset as (preset, read_only).

    list_presets() only ever returns presets that validated -- a malformed
    file is logged and left out of the listing, deliberately, so one bad
    hand-edited file cannot hide the bundled ones. Fetching that id directly
    is a different question: the id has a file, but it doesn't pass, and the
    person who dropped it into the user directory deserves to be told what's
    wrong with it rather than a bare "not found".

    Raises:
        PresetNotFound: no file with that id in either directory
        PresetInvalid: a file with that id exists but fails validation
    '''
    presets = list_presets()
    if preset_id in presets:
        return presets[preset_id]

    # Not in the listing -- either there's no such file, or it's the file
    # that got skipped. Walk the same directories, in the same shadowing
    # order as preset_dirs()/list_presets(), to find out which.
    match = None
    for directory, read_only in preset_dirs():
        path = os.path.join(directory, preset_id + ".json")
        if os.path.isfile(path):
            match = (path, read_only)

    if match is None:
        raise PresetNotFound(f"No such speaker preset: {preset_id}")

    path, read_only = match
    return load_preset_file(path, preset_id), read_only


def bank_geometry(bank_value):
    '''
    (base_address, slot_count) from a bank's 'address/cells' metadata value.

    The one place that interprets that string. Both halves must be plain
    decimal: a looser reading that only validated the cells half would let a
    bank value with a hex address (or any other address that its actual
    consumer cannot parse) pass here and then fail downstream in a way that
    looks like a bug rather than an incompatible profile.

    Returns:
        tuple or None: (base_address, slots), or None when unparsable
    '''
    if not bank_value or "/" not in str(bank_value):
        return None
    address_part, _, cells_part = str(bank_value).partition("/")
    try:
        return int(address_part), int(cells_part) // 5
    except ValueError:
        return None


def bank_slots(bank_value):
    '''
    Number of biquad slots in a bank, from its 'address/cells' metadata value.

    Returns:
        int or None: None when the value is not a bank
    '''
    geometry = bank_geometry(bank_value)
    return geometry[1] if geometry else None


def incompatibility_reason(preset, metadata):
    '''
    Why this preset cannot be applied to the loaded profile.

    Args:
        preset (dict): A validated preset
        metadata (dict): Profile metadata as returned by get_profile_metadata()

    Returns:
        str or None: None when the preset can be applied
    '''
    if not metadata or "error" in metadata:
        return "No DSP profile metadata available"

    program_id = metadata.get("programID")
    if program_id != preset["requiredProfile"]:
        return (f"Preset needs the '{preset['requiredProfile']}' DSP program, "
                f"but '{program_id or 'unknown'}' is loaded")

    try:
        version = int(metadata.get("profileVersion", 0))
    except (TypeError, ValueError):
        version = 0
    if version < preset["minProfileVersion"]:
        return (f"Preset needs {preset['requiredProfile']} version "
                f"{preset['minProfileVersion']} or newer, "
                f"version {version} is loaded")

    try:
        profile_rate = int(metadata.get("sampleRate", 0))
    except (TypeError, ValueError):
        profile_rate = 0
    if profile_rate != preset["sampleRate"]:
        # The coefficients were computed for one rate and cannot be moved to
        # another by writing them somewhere else.
        return (f"Preset coefficients are for {preset['sampleRate']} Hz, "
                f"the loaded profile runs at {profile_rate} Hz")

    for channel in CHANNELS:
        key = "IIR_" + channel.upper()
        slots = bank_slots(metadata.get(key))
        if slots is None:
            return f"Loaded profile has no filter bank {key}"
        needed = len(preset["channels"][channel]["filters"])
        if slots < needed:
            return (f"Channel {channel.upper()} needs {needed} filter slots, "
                    f"bank {key} has {slots}")

    return None


def channel_register_writes(channel, settings, metadata, sample_rate):
    '''
    The per-channel register writes a preset implies, as (address, value).

    The Python type of each value is what decides how it reaches the DSP, the
    same rule POST /memory follows: a float is converted to fixed point, an
    int is written as a raw memory word. A level arriving as int 1 would be
    memory word 1 -- silence -- so levels are always floats.

    Registers the loaded profile does not declare are skipped, which is how a
    profile with no delay lines stays usable.

    Args:
        channel (str): 'a'-'d'
        settings (dict): That channel's preset settings
        metadata (dict): Profile metadata, including '_attributes'
        sample_rate (int): Profile sample rate, for the delay conversion

    Returns:
        list: (address, value) pairs in role, level, delay, invert order

    Raises:
        PresetInvalid: the profile cannot express this channel's role
    '''
    upper = channel.upper()
    attributes = metadata.get("_attributes", {})
    writes = []

    key = "channelSelect%sRegister" % upper
    if key in metadata:
        attrs = attributes.get(key, {})
        roles = [r.strip()
                 for r in attrs.get("channels", ",".join(ROLE_FALLBACK)).split(",")]
        if settings["role"] not in roles:
            raise PresetInvalid(
                f"Channel {upper}: the loaded profile has no role "
                f"'{settings['role']}' (it offers {', '.join(roles)})")
        try:
            multiplier = int(attrs.get("multiplier", 1))
        except (TypeError, ValueError):
            multiplier = 1
        writes.append((int(metadata[key]),
                       roles.index(settings["role"]) * multiplier))

    key = "levels%sRegister" % upper
    if key in metadata:
        level = float(settings.get("level", 1.0)) if settings.get("enabled", True) else 0.0
        writes.append((int(metadata[key]), level))

    key = "delay%sRegister" % upper
    if key in metadata:
        samples = int(round(float(settings.get("delayMs", 0)) / 1000.0 * sample_rate))
        try:
            max_delay = int(attributes.get(key, {}).get("maxDelay", samples))
        except (TypeError, ValueError):
            max_delay = samples
        writes.append((int(metadata[key]), max(0, min(samples, max_delay))))

    key = "invert%sRegister" % upper
    if key in metadata:
        writes.append((int(metadata[key]), 1 if settings.get("invert") else 0))

    return writes


def summary(preset, read_only, metadata):
    '''
    The list entry for one preset: enough to render a row and say whether it
    can be applied, without shipping every coefficient.
    '''
    reason = incompatibility_reason(preset, metadata)
    return {
        "id": preset["id"],
        "name": preset["name"],
        "description": preset.get("description"),
        "requiredProfile": preset["requiredProfile"],
        "sampleRate": preset["sampleRate"],
        "readOnly": read_only,
        "filterCounts": {c: len(preset["channels"][c]["filters"])
                         for c in CHANNELS},
        "compatible": reason is None,
        "incompatibleReason": reason,
    }
