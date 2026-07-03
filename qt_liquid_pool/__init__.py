#  qt_liquid_pool/qt_liquid_pool/__init__.py
#
#  Copyright 2026 Leon Dionne <ldionne@dridesign.sh.cn>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
"""
Provides MainWindow of the kitstarter application.
"""
import logging
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtWidgets import QComboBox
from liquiphy import LiquidSFZ
from qt_extras import SigBlock
from conn_jack import JackConnectionManager, JackConnectError

__version__ = "0.0.0"


SYNTH_NAME = 'liquidsfz'
CONNECT_RETRY_INTERVAL = 1776
REGISTRATION_TIMEOUT_INTERVAL = 500


class LiquidPool(QObject):
	"""
	Handles audio, including hosting an instance of liquidsfz, and playing samples.
	"""

	__instance = None

	_sig_ports_complete = pyqtSignal()	# \
	_sig_sources_changed = pyqtSignal()	#  \
	_sig_sinks_changed = pyqtSignal()	#  | Used to decouple JackConnectionManager callbacks
	_sig_jack_down = pyqtSignal()		# /

	sig_jack_ready = pyqtSignal(bool, int)
	sig_clients_changed = pyqtSignal()
	sig_connections_changed = pyqtSignal()

	def __new__(cls):
		if cls.__instance is None:
			cls.__instance = super().__new__(cls)
		return cls.__instance

	def __init__(self):
		super().__init__()
		self._synths = []
		self._current_starting_synth = None
		self.conn_man = None

		self._preferred_midi_source = None
		self._preferred_audio_sink = None
		self.connected_midi_src_port = None
		self.connected_audio_sink_ports = []

		self._midi_in_combo = None
		self._audio_out_combo = None

		# The following signals are used internally:
		# Emitted from inside a thread created by JackConnectionManager
		# and so must use QueuedConnection in order to cross threads.

		self._sig_ports_complete.connect(self._slot_ports_complete, type = Qt.QueuedConnection)
		self._sig_sources_changed.connect(self._slot_sources_changed, type = Qt.QueuedConnection)
		self._sig_sinks_changed.connect(self._slot_sinks_changed, type = Qt.QueuedConnection)
		self._sig_jack_down.connect(self._slot_jack_down, type = Qt.QueuedConnection)

		self._client_registration_timeout_timer = QTimer(self)
		self._client_registration_timeout_timer.setInterval(REGISTRATION_TIMEOUT_INTERVAL)
		self._client_registration_timeout_timer.setSingleShot(True)
		self._client_registration_timeout_timer.timeout.connect(self._slot_client_registration_timeout)

		self.connect_retry_timer = QTimer()
		self.connect_retry_timer.setInterval(CONNECT_RETRY_INTERVAL)
		self.connect_retry_timer.setSingleShot(True)
		self.connect_retry_timer.timeout.connect(self.connect)

	# -----------------------------------------------------------------
	# Pubic methods

	def connect(self):
		try:
			self.conn_man = JackConnectionManager()
		except JackConnectError:
			self.connect_retry_timer.start()
		else:
			self.conn_man.on_error(self._jack_error)
			self.conn_man.on_shutdown(self._jack_shutdown)
			self.conn_man.on_client_registration(self._jack_client_registration)
			self.conn_man.on_port_registration(self._jack_port_registration)
			self.conn_man.on_port_connect(self._jack_port_connect)
			self.sig_jack_ready.emit(True, self.conn_man.samplerate)
			QTimer.singleShot(0, self._midi_in_combo.slot_sources_changed)
			QTimer.singleShot(0, self._audio_out_combo.slot_sinks_changed)
			self._start_next_synth()

	def create_synth(self, filename):
		"""
		Returns a Synth object
		"""
		synth = Synth(filename)
		self._synths.append(synth)
		self._start_next_synth()
		return synth

	def delete_synth(self, synth):
		"""
		Raises ValueError if not in list
		"""
		if synth is self._current_starting_synth:
			logging.warning('Deleting _current_starting_synth')
			self._current_starting_synth = None
		synth.quit()
		self._synths.remove(synth)

	@property
	def synths(self):
		return self._synths

	def quit(self):
		self._current_starting_synth = None
		for synth in self._synths:
			synth.quit()
		self._synths = []

	def midi_in_combo_box(self, parent = None):
		"""
		Returns MidiInCombo
		"""
		if self._midi_in_combo is None:
			self._midi_in_combo = MidiInCombo(self, parent)
			self._midi_in_combo.currentTextChanged.connect(self._slot_midi_src_selected)
			self._sig_sources_changed.connect(
				self._midi_in_combo.slot_sources_changed, type = Qt.QueuedConnection)
		return self._midi_in_combo

	def audio_out_combo_box(self, parent = None):
		"""
		Returns AudioOutCombo
		"""
		if self._audio_out_combo is None:
			self._audio_out_combo = AudioOutCombo(self, parent)
			self._audio_out_combo.currentTextChanged.connect(self._slot_audio_sink_selected)
			self._sig_sinks_changed.connect(
				self._audio_out_combo.slot_sinks_changed, type = Qt.QueuedConnection)
		return self._audio_out_combo

	def get_preferred_midi_source(self):
		"""
		Returns (str) the name of the port you prefer to connect to.

		Override this method to retrieve from another location, for example, a
		QSettings instance.
		"""
		return self._preferred_midi_source

	def set_preferred_midi_source(self, value):
		"""
		Sets (str) the name of the port you prefer to connect to.

		Override this method to save to another location, for example, a QSettings
		instance. Just be sure to call:

			super().set_preferred_midi_source(value)
		"""
		self._preferred_midi_source = value
		self._connect_midi_source()

	def get_preferred_audio_sink(self):
		"""
		Returns (str) the name of the client you prefer to connect to.

		Override this method to retrieve from another location, for example, a
		QSettings instance.
		"""
		return self._preferred_audio_sink

	def set_preferred_audio_sink(self, value):
		"""
		Sets (str) the name of the client you prefer to connect to.

		Override this method to save to another location, for example, a QSettings
		instance. Just be sure to call:

			super().set_preferred_audio_sink(value)
		"""
		self._preferred_audio_sink = value
		self._connect_audio_sinks()

	def disconnect_midi_source(self, port):
		"""
		Disconnects the currently connected midi source port from all synths.

		Override this method in order to manage other clients, such as an instance of
		JackAudioPlayer. Be sure to call:

			super().disconnect_midi_source(port)
		"""
		for synth in self._synths:
			self.conn_man.disconnect(port, synth.input_port)

	def connect_midi_source(self, port):
		"""
		Connects all synths to the given midi source port.

		Override this method in order to manage other clients, such as an instance of
		JackAudioPlayer. Be sure to call:

			super().connect_midi_source(port)
		"""
		for synth in self._synths:
			self.conn_man.connect(port, synth.input_port)

	def disconnect_audio_sinks(self, ports):
		"""
		Disconnects the currently connected audio sink ports from all synths.

		Override this method in order to manage other clients, such as an instance of
		JackAudioPlayer. Be sure to call:

			super().disconnect_audio_sinks(ports)
		"""
		for synth in self._synths:
			for src, tgt in zip(synth.output_ports, ports):
				self.conn_man.disconnect(src, tgt)

	def connect_audio_sinks(self, ports):
		"""
		Connects all synths to the given audio sink ports.

		Override this method in order to manage other clients, such as an instance of
		JackAudioPlayer. Be sure to call:

			super().connect_audio_sinks(ports)
		"""
		for synth in self._synths:
			for src, tgt in zip(synth.output_ports, ports):
				self.conn_man.connect(src, tgt)

	# -----------------------------------------------------------------
	# Protected methods

	def _start_next_synth(self):
		"""
		Called when a synth is registered, or when the _current_starting_synth is complete.
		"""
		if self.conn_man and self._current_starting_synth is None:
			for synth in self._synths:
				if synth.client_name is None:
					self._current_starting_synth = synth
					self._current_starting_synth.start()
					break

	def _connect_midi_source(self):
		# Look for source port if preferred_midi_source has a str value:
		if preferred_source := self.get_preferred_midi_source():
			src_port = self.conn_man.get_port_by_name(preferred_source)
			# No need to disconnect / reconnect if they are the same:
			if src_port == self.connected_midi_src_port:
				return
		else:
			src_port = None
		# Disconnect existing:
		if self.connected_midi_src_port:
			self.disconnect_midi_source(self.connected_midi_src_port)
		# Connect if preferred_midi_source has a str value:
		if src_port:
			self.connect_midi_source(src_port)
		# Update connected port (may be none):
		self.connected_midi_src_port = src_port

	def _connect_audio_sinks(self):
		# Look for target ports if preferred_audio_sink has a str value:
		if preferred_sink := self.get_preferred_audio_sink():
			tgt_ports = [ port for port
				in self.conn_man.get_client_ports(preferred_sink)
				if port.is_audio and port.is_input ]
			# No need to disconnect / reconnect if they are the same:
			if tgt_ports == self.connected_audio_sink_ports:
				return
		else:
			tgt_ports = []
		# Disconnect existing:
		if self.connected_audio_sink_ports:
			self.disconnect_audio_sinks(self.connected_audio_sink_ports)
		# Connect if preferred_audio_sink has a str value:
		if tgt_ports:
			self.connect_audio_sinks(tgt_ports)
		# Update connected ports (may be empty list):
		self.connected_audio_sink_ports = tgt_ports

	# -----------------------------------------------------------------
	# JACK callbacks

	def _jack_client_registration(self, client_name, action):
		"""
		JackConnectionManager callback.
		NOTE: This method runs in a different thread.
		"""
		if action and SYNTH_NAME in client_name:
			if self._current_starting_synth:
				self._current_starting_synth.client_name = client_name
			else:
				logging.warning('Jack registered an unknown liquidsfz instance: "%s"',
					client_name)

	def _jack_port_registration(self, port, action):
		"""
		JackConnectionManager callback.
		NOTE: This method runs in a different thread.
		"""
		if self._current_starting_synth and self._current_starting_synth.client_name in port.name:
			if port.is_input and port.is_midi:
				self._current_starting_synth.input_port = port
			elif port.is_output and port.is_audio:
				self._current_starting_synth.output_ports.append(port)
			else:
				logging.error('Incorrect port type: "%s"', port)
			if self._current_starting_synth.ports_complete():
				self._sig_ports_complete.emit()
		elif port.is_input and port.is_audio:
			self._sig_sinks_changed.emit()
		elif port.is_output and port.is_midi:
			self._sig_sources_changed.emit()

	def _jack_port_connect(self, port_a, port_b, action):
		"""
		JackConnectionManager callback.
		NOTE: This method runs in a different thread.
		"""
		self.sig_connections_changed.emit()

	def _jack_error(self, error_message):
		"""
		JackConnectionManager callback.
		NOTE: This method runs in a different thread.
		"""
		logging.error('JACK ERROR: "%s"', error_message)

	def _jack_shutdown(self):
		"""
		JackConnectionManager callback.
		NOTE: This method runs in a different thread.
		"""
		logging.warning('JACK is shutting down')
		self._sig_jack_down.emit()

	# -----------------------------------------------------------------
	# JACK callback -related slots

	@pyqtSlot()
	def _slot_ports_complete(self):
		"""
		Triggered by _sig_ports_complete from another thread
		"""
		self._client_registration_timeout_timer.stop()
		self._current_starting_synth = None
		self._start_next_synth()
		self._connect_midi_source()
		self._connect_audio_sinks()

	@pyqtSlot()
	def _slot_client_registration_timeout(self):
		"""
		Triggered by _client_registration_timeout_timer when REGISTRATION_TIMEOUT_INTERVAL
		milliseconds have passed while waiting for client name and port registration to
		complete.
		"""
		raise RuntimeError('Timed out waiting for synth registration')

	@pyqtSlot()
	def _slot_jack_down(self):
		"""
		Triggered by _sig_jack_down emitted from another thread in "_jack_shutdown"
		"""
		self.conn_man.close()
		self.conn_man = None
		self.connect_retry_timer.start()
		self.sig_jack_ready.emit(False, -1)

	# -----------------------------------------------------------------
	# Source / sink combo box management

	@pyqtSlot(str)
	def _slot_midi_src_selected(self, value):
		"""
		Triggered from combo box selection
		"""
		self.set_preferred_midi_source(value)

	@pyqtSlot(str)
	def _slot_audio_sink_selected(self, value):
		"""
		Triggered from combo box selection
		"""
		self.set_preferred_audio_sink(value)

	@pyqtSlot()
	def _slot_sources_changed(self):
		"""
		Triggered by _sig_sources_changed, emitted in "_jack_port_registration".
		"""
		self._connect_midi_source()

	@pyqtSlot()
	def _slot_sinks_changed(self):
		"""
		Triggered by _sig_sinks_changed, emitted in "_jack_port_registration".
		"""
		self._connect_audio_sinks()


class Synth(LiquidSFZ, QObject):
	"""
	Wraps a LiquidSFZ instance in order to hold references to jacklib ports created
	by JackConnectionManager.
	"""

	def __init__(self, filename):
		LiquidSFZ.__init__(self, filename, True)
		QObject.__init__(self)
		self.client_name = None
		self.input_port = None
		self.output_ports = []

	def ports_complete(self):
		"""
		Returns True if all ports are defined.
		"""
		return self.input_port and len(self.output_ports) == 2

	def delete(self):
		"""
		May be called from outside.
		"""
		LiquidPool().delete_synth(self)

	def quit(self):
		"""
		Not to be called from outside this module.
		"""
		self.input_port = None
		self.output_ports = []
		if hasattr(super(), 'quit'):
			super().quit()


class _ManagedComboBox(QComboBox):

	def __init__(self, pool, parent):
		super().__init__(parent);
		self.pool = pool


class MidiInCombo(_ManagedComboBox):

	@pyqtSlot()
	def slot_sources_changed(self):
		with SigBlock(self):
			self.clear()
			self.addItem('')
			for port in self.pool.conn_man.output_ports():
				if port.is_midi:
					self.addItem(port.name)
			source_port = self.pool.connected_midi_src_port
			if source_port and self.findText(source_port.name):
				self.setCurrentText(source_port.name)


class AudioOutCombo(_ManagedComboBox):

	@pyqtSlot()
	def slot_sinks_changed(self):
		with SigBlock(self):
			self.clear()
			self.addItem('')
			valid_clients = set(
				port.client_name for port in self.pool.conn_man.input_ports()
				if port.is_audio )
			for client in valid_clients:
				self.addItem(client)
			sink_ports = self.pool.connected_audio_sink_ports
			if sink_ports and self.findText(sink_ports[0].client_name):
				self.setCurrentText(sink_ports[0].client_name)


#  end qt_liquid_pool/qt_liquid_pool/__init__.py
