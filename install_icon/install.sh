#!/bin/bash

cp ../dist/k1usnsst ~/.local/bin/

xdg-icon-resource install --size 64 --context apps --mode user ../icon/K1USN-SST.png k6gte-k1usnsst

xdg-desktop-icon install k6gte-k1usnsst.desktop

xdg-desktop-menu install k6gte-k1usnsst.desktop

