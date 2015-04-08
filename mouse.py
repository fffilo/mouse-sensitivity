#!/usr/bin/python
#-- coding: utf-8 --

### import modules
import os, gtk, dbus, appindicator, pynotify, subprocess, json, re, copy

### app properties
__author__ = 'Franjo Filo <fffilo666@gmail.com>'
__version__ = '0.1'
__title__ = 'mouse-sensitivity'
__copyright__ = 'Copyright (c) 2015\n' + __author__
__icon__ = os.path.dirname(os.path.realpath(__file__)) + '/icon.png'
__config__ = os.path.expanduser('~') + '/.' + __title__ + '.json'

### global variables
_devices = None
_notice = None
_indicator = None
_menu_main = None
_menu_devices = None
_menu_main_devices = None
_menu_sensitivity = None
_menu_main_sensitivity = None
_menu_sensitivity_increase = None
_menu_sensitivity_decrease = None
_menu_sensitivity_reset = None
_menu_main_about = None
_menu_main_quit = None
_dialog = None

### global constants
_min = 0.2
_max = 5.0
_step = 0.1

### check if application is already running
def _single():
	if dbus.SessionBus().request_name('com.fffilo.mouse-sensitivity') != dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:
		print 'Application already running...'

		dialog = gtk.MessageDialog(None, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, 'Another instance of ' + __title__ + ' is already running. Please close the running instance before starting a new one.')
		dialog.run()
		dialog.destroy()

		print 'Quiting...'

		exit(0)

### check if xinput utility exists and get devices
def _xinput():
	global _devices

	if not subprocess.call('type xinput', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0:
		print 'This application depends on xinput utility...'
		exit()

	p = subprocess.Popen('xinput', stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
	s = str(p.communicate()).decode('string_escape')
	f = re.findall(r'\sid=(\d+).*slave\s+pointer', str(s))

	_devices = []
	for ids in f:
		device = { 'id': int(ids), 'name': 'Unknown device', 'enabled': False, 'submenu': None }

		p = subprocess.Popen(['xinput', 'list-props', str(ids)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
		s = str(p.communicate()).decode('string_escape')

		m = re.search(r'Device \'(.*)\':', str(s))
		if not m is None: device['name'] = m.group(1)

		m = re.search(r'Device Enabled.*:\s*([0-9\.]+)', str(s))
		if not m is None: device['enabled'] = not not int(m.group(1))

		m = re.search(r'Device Accel Constant Deceleration.*:\s*([0-9\.]+)', str(s))
		if m is None: device['enabled'] = False

		_devices.append(device)

### create menu, menu items, indicator, notice
def _create():
	global _notice, _indicator, _menu_main, _menu_devices, _menu_main_devices, _menu_sensitivity, _menu_main_sensitivity, _menu_sensitivity_increase, _menu_sensitivity_decrease, _menu_sensitivity_reset, _menu_main_about, _menu_main_quit

	_menu_main = gtk.Menu()
	_menu_devices = gtk.Menu()
	_menu_main_devices = gtk.MenuItem('Pointer devices')
	_menu_main_devices.set_submenu(_menu_devices)
	_menu_main_devices.show();
	_menu_main.append(_menu_main_devices)
	item = gtk.SeparatorMenuItem()
	item.show()
	_menu_main.append(item)
	_menu_sensitivity = gtk.Menu()
	_menu_main_sensitivity = gtk.MenuItem('Sensitivity')
	_menu_main_sensitivity.set_submenu(_menu_sensitivity)
	_menu_main_sensitivity.set_sensitive(False)
	_menu_main_sensitivity.show();
	_menu_main.append(_menu_main_sensitivity)
	item = gtk.SeparatorMenuItem()
	item.show()
	_menu_main.append(item)
	_menu_sensitivity_increase = gtk.MenuItem('Increase')
	_menu_sensitivity_increase.connect('activate', _increase)
	_menu_sensitivity_increase.set_sensitive(False)
	_menu_sensitivity_increase.show()
	_menu_sensitivity.append(_menu_sensitivity_increase)
	_menu_sensitivity_decrease = gtk.MenuItem('Decrease')
	_menu_sensitivity_decrease.connect('activate', _decrease)
	_menu_sensitivity_decrease.set_sensitive(False)
	_menu_sensitivity_decrease.show()
	_menu_sensitivity.append(_menu_sensitivity_decrease)
	item = gtk.SeparatorMenuItem()
	item.show()
	_menu_sensitivity.append(item)
	_menu_sensitivity_reset = gtk.MenuItem('Reset')
	_menu_sensitivity_reset.set_sensitive(False)
	_menu_sensitivity_reset.connect('activate', _reset)
	_menu_sensitivity_reset.show()
	_menu_sensitivity.append(_menu_sensitivity_reset)
	_menu_main_about = gtk.MenuItem('About')
	_menu_main_about.connect('activate', _about)
	_menu_main_about.show()
	_menu_main.append(_menu_main_about)
	item = gtk.SeparatorMenuItem()
	item.show()
	_menu_main.append(item)
	_menu_main_quit = gtk.MenuItem('Quit')
	_menu_main_quit.connect('activate', _quit)
	_menu_main_quit.show()
	_menu_main.append(_menu_main_quit)

	for device in _devices:
		device['submenu'] = gtk.CheckMenuItem(device['name'])
		device['submenu'].set_sensitive(device['enabled'])
		device['submenu'].connect('activate', _check)
		device['submenu'].show()
		_menu_devices.append(device['submenu'])

	config = _cfg_read()
	if type(config) is list:
		for item in config:
			if type(item) is dict:
				if item['checked'] and item['id']:
					for device in _devices:
						if device['id'] == item['id']:
							device['submenu'].set_active(True)

	_indicator = appindicator.Indicator(__title__, __icon__, appindicator.CATEGORY_APPLICATION_STATUS)
	_indicator.set_status(appindicator.STATUS_ACTIVE)
	_indicator.connect('scroll-event', _scroll)
	_indicator.set_menu(_menu_main)

	pynotify.init(__title__)
	_notice = pynotify.Notification(__title__, 'Mouse sensitivity at 100.0%', __icon__)

### get config from file
def _cfg_read():
	result = {}

	if os.path.isfile(__config__):
		try:
			f = open(__config__)
			result = json.loads(f.read())
			f.close()
		except Exception:
			pass

	return result

### set config in file
def _cfg_write():
	result = []
	for device in _devices:
		item = copy.copy(device)
		item['checked'] = False
		if item['submenu'] and item['submenu'].get_active():
			item['checked'] = True
		del item['submenu']
		result.append(item)

	try:
		f = open(__config__, 'w')
		f.write(json.dumps(result, default=lambda o: o.__dict__, indent=4))
		f.close()
	except Exception as e:
		pass

### get sensitivity value
def _value(id):
	result = 1

	p = subprocess.Popen(['xinput', 'list-props', str(id)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
	s = str(p.communicate()).decode('string_escape')
	m = re.search(r'Device Accel Constant Deceleration.*:\s*([0-9\.]+)', str(s))
	if m != None:
		try:
			result = float(m.group(1))
		except Exception, e:
			pass

	return result

### set sensitivity value
def _exec(value):
	for device in _devices:
		if device['submenu'].get_active():
			cur = _value(device['id'])
			val = value

			if val == '+': val = cur + _step
			if val == '-': val = cur - _step
			if val < _min: val = _min
			if val > _max: val = _max
			if val == _value(device['id']): return

			print 'Executing command: ' + 'xinput set-prop ' + str(device['id']) + ' "Device Accel Constant Deceleration" ' + str(val)
			subprocess.Popen(['xinput', 'set-prop', str(device['id']), 'Device Accel Constant Deceleration', str(val)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

			_notice.update(device['name'], 'Mouse sensitivity at ' + str(float(val * 100)) + '%', __icon__)
			#_notice.set_timeout(1000)
			_notice.show()

### on mousescroll event
def _scroll(indicator, steps, direction):
	if direction == gtk.gdk.SCROLL_UP: _increase()
	if direction == gtk.gdk.SCROLL_DOWN: _decrease()

### check device
def _check(item):
	global _checking

	try:
		_checking
	except Exception, e:
		_checking = True
		for device in _devices:
			if device['submenu']:
				device['submenu'].set_active(False)

		_menu_main_sensitivity.set_sensitive(True)
		_menu_sensitivity_increase.set_sensitive(True)
		_menu_sensitivity_decrease.set_sensitive(True)
		_menu_sensitivity_reset.set_sensitive(True)

		item.set_active(True)

		_cfg_write()

		print 'Slave pointer xinput "' + str(item.get_label()) + '"'

		del _checking

### reset sensitivity
def _reset(item=None):
	if _menu_sensitivity_reset.get_sensitive():
		_exec(1)

### increase sensitivity
def _increase(item=None):
	if _menu_sensitivity_increase.get_sensitive():
		_exec('+')

### decrease sensitivity
def _decrease(item=None):
	if _menu_sensitivity_decrease.get_sensitive():
		_exec('-')

### display about dialog
def _about(item=None):
	global _dialog

	_menu_main_about.set_sensitive(False)

	if _dialog is None:
		print 'Opening about dialog...'
		icon = gtk.gdk.pixbuf_new_from_file(__icon__)
		_dialog = gtk.AboutDialog()
		_dialog.set_name(__title__)
		#_dialog.set_version(__version__)
		_dialog.set_copyright(__copyright__)
		_dialog.set_logo(icon)
		_dialog.set_icon(icon)
		#_dialog.set_icon_from_file(__icon__)
		_dialog.run()

		print 'Closing about dialog...'
		_menu_main_about.set_sensitive(True)
		_dialog.destroy()
		_dialog = None

### quit app
def _quit(item=None):
	print 'Quit menu clicked. Quiting...'
	if not _dialog is None:
		_dialog.destroy()
	gtk.main_quit()

### initialize
_single()
_xinput()
_create()
_reset()

### go, go, go...
try:
	gtk.main()
except KeyboardInterrupt:
	print 'User keyboard interrupt occured. Quiting...'
except:
	print 'Error...'
