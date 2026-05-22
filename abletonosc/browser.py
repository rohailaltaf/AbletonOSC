from typing import Tuple, Any

import Live

from .handler import AbletonOSCHandler


class BrowserHandler(AbletonOSCHandler):
    """OSC handlers for walking and loading from Live's browser.

    Exposes the MIDI-effect side (`app.browser.midi_effects`) for adding
    Arpeggiator / Scale / Chord / Note Length and other note processors onto
    MIDI tracks. The instrument, drum, audio-effect and sample sections follow
    the same walk-and-load pattern.
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

        def list_midi_effects(params: Tuple[Any]):
            path = str(params[0]) if params else ""
            app = Live.Application.get_application()
            node = _walk(app.browser.midi_effects, path) if path else app.browser.midi_effects
            if node is None:
                # Bad path — reply with just the path so callers can disambiguate
                # from "valid path, no children".
                self.osc_server.send(
                    "/live/browser/list_midi_effects", (path,)
                )
                return
            names = tuple(child.name for child in node.children)
            self.osc_server.send(
                "/live/browser/list_midi_effects", (path,) + names
            )

        def load_midi_effect(params: Tuple[Any]):
            track_id = int(params[0])
            path = str(params[1])
            if not path:
                self.logger.warning("load_midi_effect: empty path")
                return

            app = Live.Application.get_application()
            node = _walk(app.browser.midi_effects, path)
            if node is None:
                return
            if not node.is_loadable:
                self.logger.warning(
                    "load_midi_effect: path %r is not loadable" % path
                )
                return

            try:
                track = self.song.tracks[track_id]
            except IndexError:
                self.logger.warning(
                    "load_midi_effect: track %d does not exist" % track_id
                )
                return

            self.song.view.selected_track = track
            app.browser.load_item(node)

        self.osc_server.add_handler(
            "/live/browser/list_midi_effects", list_midi_effects
        )
        self.osc_server.add_handler(
            "/live/track/load_midi_effect", load_midi_effect
        )
