from typing import Tuple, Any

import Live

from .handler import AbletonOSCHandler


class BrowserHandler(AbletonOSCHandler):
    """OSC handlers for walking and loading from Live's browser.

    Exposes the instrument-side (`app.browser.instruments`) for "I want a synth"
    workflows and the drum-side (`app.browser.drums`) for "I want a drum kit"
    workflows. Audio effects, MIDI effects, etc. could follow the same pattern.
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

        def list_drum_kits(params: Tuple[Any]):
            path = str(params[0]) if params else ""
            app = Live.Application.get_application()
            node = _walk(app.browser.drums, path) if path else app.browser.drums
            if node is None:
                self.osc_server.send("/live/browser/list_drum_kits", (path,))
                return
            names = tuple(child.name for child in node.children)
            self.osc_server.send(
                "/live/browser/list_drum_kits", (path,) + names
            )

        def load_drum_kit(params: Tuple[Any]):
            track_id = int(params[0])
            path = str(params[1])
            if not path:
                self.logger.warning("load_drum_kit: empty path")
                return

            app = Live.Application.get_application()
            node = _walk(app.browser.drums, path)
            if node is None:
                return
            if not node.is_loadable:
                self.logger.warning(
                    "load_drum_kit: path %r is not loadable" % path
                )
                return

            try:
                track = self.song.tracks[track_id]
            except IndexError:
                self.logger.warning(
                    "load_drum_kit: track %d does not exist" % track_id
                )
                return

            self.song.view.selected_track = track
            app.browser.load_item(node)

        self.osc_server.add_handler(
            "/live/browser/list_instrument_presets", list_instrument_presets
        )
        self.osc_server.add_handler(
            "/live/track/load_instrument_preset", load_instrument_preset
        )
        self.osc_server.add_handler(
            "/live/browser/list_drum_kits", list_drum_kits
        )
        self.osc_server.add_handler(
            "/live/track/load_drum_kit", load_drum_kit
        )
