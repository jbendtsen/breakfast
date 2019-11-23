# Breakfast
A tool for analysing and controlling serial devices in Unix

## Features
* Send and receive data asynchronously
* Pipe incoming data through shell command (filter)
* Macros (in Python) for custom functionality
* Optional key binding for each macro
* Multiple tabs, each with their own data, filter and macro

## Usage
```
python breakfast.py
python breakfast.py /dev/ttyUSB1
```
The device used by default is `/dev/ttyUSB0`.

To use this tool without a device, pass in `/dev/null`.
