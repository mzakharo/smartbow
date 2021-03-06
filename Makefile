.EXPORT_ALL_VARIABLES:
P4A_RELEASE_KEYALIAS ?= cb-play
P4A_RELEASE_KEYSTORE_PASSWD ?= 123456
P4A_RELEASE_KEYALIAS_PASSWD ?= 123456

dir_path :=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
P4A_RELEASE_KEYSTORE ?= $(dir_path)/keystore/this.keystore

BIN= $(shell mkdir -p bin)
APK=$(shell ls --sort=time bin/ -r | tail -1)

release:
	python3 version.py
	buildozer android release

install:
	adb install -r bin/$(APK)
