PREFIX ?= /usr/local

install:
	install -m 755 scripts/kessel $(PREFIX)/bin/kessel
