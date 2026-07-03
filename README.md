# qt_liquid_pool

Manages port connections for instances of LiquidSFZ using JackConnectionManager.

## Purpose

This library:

1. Instantiates any number of instances of LiquidSFZ from the "liquiphy"
package.

2. Creates a connection to the JACK audio connection kit and monitors changes
in clients and ports for the purpose of managing the ports created by the
above-mentioned LiquidSFZ instances.

3. Optionally fills and updates two instances of QComboBox, which may be used
in your project for allowing a user to select input and output devices to
connect to the LiquidSFZ instance(s).

I found myself using the same blocks of code in several projects, and decided
to break these out into a new project which could be generally reused.

## Installation

Install from the pypi repository:

```bash
$ pip install qt_liquid_pool
```

## Usage:

Import

```python
from qt_liquid_pool import LiquidPool
```

### Extending for custom features

You can write your own class which inherits from LiquidPool in order to provide
additional features.

#### Additional devices

The following class connects and disconnects a soundfile player alongside the
built-in instances of LiquidSFZ:


```python
class Audio(LiquidPool):

	def __init__(self):
		super().__init__()
		self.audio_player = None

	def slot_jack_ready(self, state):
		if state:
			self.audio_player = JackAudioPlayer(AUDIO_PLAYER_CLIENT)

	def disconnect_audio_sinks(self, ports):
		super().disconnect_audio_sinks(ports)
		for src, tgt in zip(self.audio_player.output_ports, ports):
			self.conn_man.disconnect(src, tgt)

	def connect_audio_sinks(self, ports):
		super().connect_audio_sinks(ports)
		for src, tgt in zip(self.audio_player.output_ports, ports):
			self.conn_man.connect(src, tgt)

	def play_soundfile(self, soundfile):
		soundfile.seek(0)
		self.audio_player.play_python_soundfile(soundfile)

	def stop_playing(self):
		self.audio_player.stop()

```

#### Saved preferred connections

There is no persistent storage mechanism built in which can save and restore
your preferred midi input and audio output devices. The following example shows
you you can save and restore these values to a QSettings settings object:

```python
class Audio(LiquidPool):

	def __init__(self):
		super().__init__()
		self.settings = QSettings('developer', 'app')

	def get_preferred_midi_source(self):
		return settings.value('MIDISource')

	def set_preferred_midi_source(self, value):
		settings.setValue('MIDISource', value)
		super().set_preferred_midi_source(value)

	def get_preferred_audio_sink(self):
		return settings.value('AudioSink')

	def set_preferred_audio_sink(self, value):
		settings.setValue('AudioSink', value)
		super().set_preferred_audio_sink(value)

```
