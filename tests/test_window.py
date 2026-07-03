#  qt_liquid_pool/tests/test_window.py
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
Creates a test dialog for testing LiquidPool.
"""
import sys, logging
from os.path import dirname, join
from PyQt5.QtWidgets import (
	QApplication, QDialog, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
	QVBoxLayout, QHBoxLayout)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer, QSize
from qt_liquid_pool import LiquidPool

CONNECTED = 'Connected'
NOT_CONNECTED = 'Not connected'
DEBOUNCE_INTERVAL = 125


class Dialog(QDialog):

	def __init__(self):
		super().__init__()
		self.liquid_pool = LiquidPool()
		self.midi_in_combo = self.liquid_pool.midi_in_combo_box(self)
		self.audio_out_combo = self.liquid_pool.audio_out_combo_box(self)
		self.connection_status_label = QLabel(NOT_CONNECTED, self)
		self.create_synth_button = QPushButton('Create synth', self)
		self.connections_table = QTableWidget(self)
		self.connections_table.setColumnCount(2)
		lo = QVBoxLayout()
		hlo = QHBoxLayout()
		hlo.addWidget(QLabel('MIDI Input port:', self))
		hlo.addWidget(self.midi_in_combo)
		lo.addLayout(hlo)
		hlo = QHBoxLayout()
		hlo.addWidget(QLabel('Audio output client:', self))
		hlo.addWidget(self.audio_out_combo)
		lo.addLayout(hlo)
		lo.addWidget(self.create_synth_button)
		lo.addWidget(self.connections_table)
		hlo = QHBoxLayout()
		lbl = QLabel('Connection status:', self)
		lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		hlo.addWidget(lbl)
		hlo.addWidget(self.connection_status_label)
		lo.addLayout(hlo)
		self.setLayout(lo)
		self.setWindowTitle('LiquidPool test window')
		self.liquid_pool.sig_jack_ready.connect(self.slot_jack_ready)
		self.connection_debounce_timer = QTimer(self)
		self.connection_debounce_timer.setInterval(DEBOUNCE_INTERVAL)
		self.connection_debounce_timer.setSingleShot(True)
		self.connection_debounce_timer.timeout.connect(self.slot_connections_changed)
		self.liquid_pool.sig_connections_changed.connect(self.connection_debounce_timer.start)
		self.create_synth_button.clicked.connect(self.slot_create_synth)
		QTimer.singleShot(0, self.liquid_pool.connect)

	def sizeHint(self):
		return QSize(700, 500)

	@pyqtSlot(bool)
	def slot_jack_ready(self, state):
		self.connection_status_label.setText(CONNECTED if state else NOT_CONNECTED)

	@pyqtSlot()
	def slot_create_synth(self):
		self.liquid_pool.create_synth(join(dirname(__file__), 'empty.sfz'))

	@pyqtSlot()
	def slot_connections_changed(self):
		self.connections_table.clear()
		table_row = 0
		for synth in self.liquid_pool.synths:
			in_connections = [] if synth.input_port is None else [ (port, synth.input_port)
				for port in self.liquid_pool.conn_man.get_port_connections(synth.input_port) ]
			out_connections = []
			for synth_out_port in synth.output_ports:
				out_connections.extend([ (synth_out_port, port)
					for port in self.liquid_pool.conn_man.get_port_connections(synth_out_port) ])
			rows_needed = max(len(in_connections), len(out_connections))
			self.connections_table.setRowCount(table_row + rows_needed)
			for row, tup in enumerate(in_connections):
				self.connections_table.setItem(table_row + row, 0, QTableWidgetItem(
					f'{tup[0].name} -> {tup[1].name}'))
			for row, tup in enumerate(out_connections):
				self.connections_table.setItem(table_row + row, 1, QTableWidgetItem(
					f'{tup[0].name} -> {tup[1].name}'))
			table_row += rows_needed
		self.connections_table.resizeColumnsToContents()

if __name__ == "__main__":
	logging.basicConfig(
		level = logging.DEBUG,
		format = "[%(filename)24s:%(lineno)-4d] %(levelname)-8s %(message)s"
	)
	app = QApplication([])
	dialog = Dialog()
	dialog.exec_()
	sys.exit(0)


#  end qt_liquid_pool/tests/test_window.py
