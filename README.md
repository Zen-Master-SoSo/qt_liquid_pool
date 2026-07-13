# qt_liquid_pool

Manages port connections for instances of LiquidSFZ using JackConnectionManager.

## Purpose

I found myself using the same blocks of code in several projects, and decided
to break these out into a new project which could be generally reused.

This library:

1. Instantiates any number of instances of LiquidSFZ from the "liquiphy"
package.

2. Creates a connection to the JACK audio connection kit and monitors changes
in clients and ports for the purpose of managing the ports created by the
above-mentioned LiquidSFZ instances.

3. Optionally fills and updates two instances of QComboBox, which may be used
in your project for allowing a user to select input and output devices to
connect to the LiquidSFZ instance(s).

Here's a screenshot of the test window, showing two combo boxes for source/sink
selection, and a table displaying instantiated synth ports and their connections:

<img width="635" height="379" alt="test-window" src="https://github.com/user-attachments/assets/0615fb7e-203d-44a3-9c36-c795dd5f3e05" />

## Installation

Install from the pypi repository:

```bash
$ pip install qt_liquid_pool
```

You'll need both [JACK audio connection kit](https://jackaudio.org/) and
[liquidsfz](https://github.com/swesterfeld/liquidsfz).

To install JACK:

```bash
$ sudo apt install jackd
```

...or...

```bash
$ sudo dnf install jackd
```

To install liquidsfz:

```bash
$ git clone https://github.com/swesterfeld/liquidsfz.git
```

... and follow the instructions found in the liquidsfz README to install it.


## Usage:

Import

```python
from qt_liquid_pool import LiquidPool
```

Here's an excerpt from the test window shown above, demonstrating some basic usage:

```python
class Dialog(QDialog):

	def __init__(self):
		super().__init__()
		self.liquid_pool = LiquidPool()
		self.midi_in_combo = self.liquid_pool.midi_in_combo_box(self)
		self.audio_out_combo = self.liquid_pool.audio_out_combo_box(self)
		[...]
		hlo.addWidget(self.midi_in_combo)
		hlo.addWidget(self.audio_out_combo)
		[...]
		self.liquid_pool.sig_jack_ready.connect(self.slot_jack_ready)
		self.liquid_pool.sig_connections_changed.connect(self.slot_connections_changed)
		QTimer.singleShot(0, self.liquid_pool.connect)

	@pyqtSlot(bool)
	def slot_jack_ready(self, state):
		self.connection_status_label.setText(CONNECTED if state else NOT_CONNECTED)

	@pyqtSlot()
	def slot_connections_changed(self):
		[...]

```

### Extending for custom features

You can write your own class which inherits from LiquidPool in order to provide
additional features. In particular, the "connect_midi_source" and "connect_audio_sinks"
methods have been broken out for the specific purpose of making them extensible. The
same goes for the "get/set_preferred_midi_source" and "get/set_preferred_audio_sink"
methods.

The following two examples show how these methods can be overriden to provide
new capabilities:

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
			self.audio_player = JackAudioPlayer('my-audio-player')

	def disconnect_audio_sinks(self, ports):
		"""
		Disconnects the currently connected audio sink ports from all synths.
		"ports" is a list of currently connected audio sink ports, (usually two).
		"""
		super().disconnect_audio_sinks(ports)
		for src, tgt in zip(self.audio_player.output_ports, ports):
			self.conn_man.disconnect(src, tgt)

	def connect_audio_sinks(self, ports):
		"""
		Connects all synths to the given audio sink ports.
		"ports" is a list of audio sink ports to connect to, (usually two).
		"""
		super().connect_audio_sinks(ports)
		for src, tgt in zip(self.audio_player.output_ports, ports):
			self.conn_man.connect(src, tgt)

	def play_soundfile(self, soundfile):
		soundfile.seek(0)
		self.audio_player.play_python_soundfile(soundfile)

	def stop_playing(self):
		self.audio_player.stop()

```

#### Saving preferred connections

There is no persistent storage mechanism built in which can save and restore
your preferred midi input and audio output devices. The following example shows
you you can save and restore these values to a QSettings settings object:

```python
class Audio(LiquidPool):

	def __init__(self):
		super().__init__()
		self.settings = QSettings('developer', 'app')

	def get_preferred_midi_source(self):
		"""
		Returns (str) the name of the port you prefer to connect to.
		"""
		return settings.value('MIDISource')

	def set_preferred_midi_source(self, value):
		"""
		Sets (str) the name of the port you prefer to connect to.
		"""
		settings.setValue('MIDISource', value)
		super().set_preferred_midi_source(value)

	def get_preferred_audio_sink(self):
		"""
		Returns (str) the name of the client you prefer to connect to.
		"""
		return settings.value('AudioSink')

	def set_preferred_audio_sink(self, value):
		"""
		Sets (str) the name of the client you prefer to connect to.
		"""
		settings.setValue('AudioSink', value)
		super().set_preferred_audio_sink(value)

```
