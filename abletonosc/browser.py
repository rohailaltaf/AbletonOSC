from typing import Tuple, Any

import Live

from .handler import AbletonOSCHandler


class BrowserHandler(AbletonOSCHandler):
    """OSC handlers for walking and loading from Live's browser.

    Exposes the instrument-side (`app.browser.instruments`) for "I want a synth"
    workflows and the samples library (`app.browser.samples`) so callers can
    load actual audio samples — vocal chops, drum hits, percussion loops — as
    Simpler instances on MIDI tracks. MIDI effects, drums, audio effects, etc.
    follow the same pattern in adjacent feature branches.
    """

    def __init__(self, manager):
        super().__init__(manager)
        self.class_identifier = "browser"

    def init_api(self):
        def _walk(root, path: str):
            """Walk `root.children` by slash-separated `path`. Returns the
            terminal BrowserItem, or None if any segment misses."""
            node = root
            for segment in path.split("/"):
                if not segment:
                    continue
                matched = None
                for child in node.children:
                    if child.name == segment:
                        matched = child
                        break
                if matched is None:
                    self.logger.warning(
                        "browser walk: no child named %r under %r"
                        % (segment, node.name)
                    )
                    return None
                node = matched
            return node

        def list_instrument_presets(params: Tuple[Any]):
            path = str(params[0]) if params else ""
            app = Live.Application.get_application()
            node = _walk(app.browser.instruments, path) if path else app.browser.instruments
            if node is None:
                # Bad path — reply with just the path so callers can disambiguate
                # from "valid path, no children".
                self.osc_server.send(
                    "/live/browser/list_instrument_presets", (path,)
                )
                return
            names = tuple(child.name for child in node.children)
            self.osc_server.send(
                "/live/browser/list_instrument_presets", (path,) + names
            )

        def load_instrument_preset(params: Tuple[Any]):
            track_id = int(params[0])
            path = str(params[1])
            if not path:
                self.logger.warning("load_instrument_preset: empty path")
                return

            app = Live.Application.get_application()
            node = _walk(app.browser.instruments, path)
            if node is None:
                return
            if not node.is_loadable:
                self.logger.warning(
                    "load_instrument_preset: path %r is not loadable" % path
                )
                return

            try:
                track = self.song.tracks[track_id]
            except IndexError:
                self.logger.warning(
                    "load_instrument_preset: track %d does not exist" % track_id
                )
                return

            self.song.view.selected_track = track
            app.browser.load_item(node)

        def list_samples(params: Tuple[Any]):
            # Params: (path) or (path, offset). Optional offset for pagination
            # when a folder has more children than fit in one OSC packet.
            path = str(params[0]) if len(params) >= 1 else ""
            offset = int(params[1]) if len(params) >= 2 else 0

            app = Live.Application.get_application()
            node = _walk(app.browser.samples, path) if path else app.browser.samples
            if node is None:
                # Bad path — reply with (path, offset, 0) so callers can
                # disambiguate from "valid path, no children".
                self.osc_server.send(
                    "/live/browser/list_samples", (path, offset, 0)
                )
                return

            all_children = list(node.children)
            total = len(all_children)

            # Cap the reply by accumulated byte size to stay under typical
            # OSC/UDP MTU (~9 KB on macOS). When truncated, callers can
            # re-request with offset = previous_offset + len(returned_names).
            MAX_REPLY_BYTES = 7500
            names = []
            # path string + (offset, total) ints + osc framing overhead
            running = len(path.encode("utf-8")) + 64
            for child in all_children[offset:]:
                name = child.name
                nb = len(name.encode("utf-8")) + 8
                if running + nb > MAX_REPLY_BYTES:
                    break
                names.append(name)
                running += nb

            # Reply shape: (path, offset, total_count, name1, name2, ...)
            self.osc_server.send(
                "/live/browser/list_samples",
                (path, offset, total) + tuple(names),
            )

        def load_sample(params: Tuple[Any]):
            track_id = int(params[0])
            path = str(params[1])
            if not path:
                self.logger.warning("load_sample: empty path")
                return

            app = Live.Application.get_application()
            node = _walk(app.browser.samples, path)
            if node is None:
                return
            if not node.is_loadable:
                self.logger.warning(
                    "load_sample: path %r is not loadable" % path
                )
                return

            try:
                track = self.song.tracks[track_id]
            except IndexError:
                self.logger.warning(
                    "load_sample: track %d does not exist" % track_id
                )
                return

            # Loading a sample onto a track wraps it in a Simpler automatically.
            self.song.view.selected_track = track
            app.browser.load_item(node)

        self.osc_server.add_handler(
            "/live/browser/list_instrument_presets", list_instrument_presets
        )
        self.osc_server.add_handler(
            "/live/track/load_instrument_preset", load_instrument_preset
        )
        def load_sample_to_drum_pad(params: Tuple[Any]):
            """Load a sample into a specific Drum Rack pad on a track.

            Params: (track_id, device_id, pad_pitch, path) where pad_pitch
            is the MIDI note that triggers the pad (e.g. 36 = kick, 38 =
            snare in General-MIDI-style Drum Rack layouts).
            """
            track_id = int(params[0])
            device_id = int(params[1])
            pad_pitch = int(params[2])
            path = str(params[3])
            if not path:
                self.logger.warning("load_sample_to_drum_pad: empty path")
                return

            app = Live.Application.get_application()
            node = _walk(app.browser.samples, path)
            if node is None:
                return
            if not node.is_loadable:
                self.logger.warning(
                    "load_sample_to_drum_pad: path %r is not loadable" % path
                )
                return

            try:
                track = self.song.tracks[track_id]
            except IndexError:
                self.logger.warning(
                    "load_sample_to_drum_pad: track %d does not exist" % track_id
                )
                return

            try:
                device = track.devices[device_id]
            except IndexError:
                self.logger.warning(
                    "load_sample_to_drum_pad: device %d does not exist on track %d"
                    % (device_id, track_id)
                )
                return

            if not hasattr(device, "drum_pads"):
                self.logger.warning(
                    "load_sample_to_drum_pad: device %d on track %d is not a Drum Rack"
                    % (device_id, track_id)
                )
                return

            try:
                pad = device.drum_pads[pad_pitch]
            except (IndexError, KeyError):
                self.logger.warning(
                    "load_sample_to_drum_pad: no drum pad at MIDI pitch %d"
                    % pad_pitch
                )
                return

            # Selecting the pad as the active drop target, then load.
            self.song.view.selected_track = track
            device.view.selected_drum_pad = pad
            app.browser.load_item(node)

        self.osc_server.add_handler(
            "/live/browser/list_samples", list_samples
        )
        self.osc_server.add_handler(
            "/live/track/load_sample", load_sample
        )
        self.osc_server.add_handler(
            "/live/track/load_sample_to_drum_pad", load_sample_to_drum_pad
        )
