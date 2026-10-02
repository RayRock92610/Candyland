PREFIX ?= /data/data/com.termux/files/usr
BINDIR ?= $(PREFIX)/bin

install:
	install -d $(BINDIR)
	install -m 755 scripts/kessel $(BINDIR)/kessel

uninstall:
	rm -f $(BINDIR)/kessel
