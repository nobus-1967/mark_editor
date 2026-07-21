#!/bin/bash

# Mark Editor Makefile
# For building executable and AppImage

APP_NAME="mark_editor"
MAIN_FILE="mark_editor.py"
REQUIREMENTS="requirements.txt"
VENV_DIR="venv"

# Create virtual environment and install dependencies
setup:
	python3 -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install -r $(REQUIREMENTS)
	@echo "Virtual environment created and dependencies installed"

# Activate virtual environment and run commands
activate:
	@echo "Run: source $(VENV_DIR)/bin/activate"

# Install dependencies in existing venv
install-deps:
	$(VENV_DIR)/bin/pip install -r $(REQUIREMENTS)

# Create standalone executable using PyInstaller
executable:
	$(VENV_DIR)/bin/pip install pyinstaller
	$(VENV_DIR)/bin/pyinstaller --onefile \
		--add-binary /usr/bin/pandoc:. \
		--add-data images/mark_editor.svg:images \
		--add-data images/mark_editor.png:images \
		--add-data $(VENV_DIR)/lib/python3.14/site-packages/ttkbootstrap/assets:ttkbootstrap/assets \
		--hidden-import pymdownx.caret \
		--hidden-import pymdownx.tilde \
		--hidden-import pymdownx.mark \
		--hidden-import pymdownx.smartsymbols \
		--hidden-import pymdownx \
		--hidden-import PIL._tkinter_finder \
		--name $(APP_NAME) $(MAIN_FILE)
	@echo "Executable created in dist/$(APP_NAME)"

# Create AppImage (requires executable target to have been run first)
appimage:
	$(VENV_DIR)/bin/pip install appimage-builder
	mkdir -p AppDir/usr/bin
	mkdir -p AppDir/usr/share/applications

	cp dist/$(APP_NAME) AppDir/usr/bin/
	cp AppDir/usr/bin/$(APP_NAME) AppDir/$(APP_NAME)
	mkdir -p AppDir/usr/share/icons/hicolor/scalable/apps
	cp images/mark_editor.svg AppDir/usr/share/icons/hicolor/scalable/apps/$(APP_NAME).svg

	printf '[Desktop Entry]\nType=Application\nName=Mark Editor\nExec=%s\nIcon=%s\nCategories=TextEditor;\n' $(APP_NAME) $(APP_NAME) > AppDir/$(APP_NAME).desktop

	$(VENV_DIR)/bin/appimage-builder --recipe AppImageBuilder.yml
	@echo "AppImage created"

# Run the application
run:
	$(VENV_DIR)/bin/python $(MAIN_FILE)

# Run tests
test:
	$(VENV_DIR)/bin/python test_editor.py

# Clean build artifacts
clean:
	rm -rf build *.spec AppDir appimage-build __pycache__ .pytest_cache .ruff_cache AppDir.squashfs *.zsync .bundle.yml
	@echo "Cleaned build artifacts"

# Clean everything including venv
clean-all: clean
	rm -rf $(VENV_DIR)
	@echo "Virtual environment removed"

# Install for development
dev: setup
	@echo "Development environment ready"

.PHONY: setup activate install-deps executable appimage run test clean clean-all dev
