# Breakfast
A tool for analysing and controlling serial devices in Unix

## Features
* Send and receive data asynchronously
* Pipe incoming data through a shell command, which provides a "filter"
* Multiple tabs, each containing their own received data and filter
* Edit recevied data in unfiltered mode

## Usage
```
python breakfast.py
python breakfast.py /dev/ttyUSB1
```
The device used by default is `/dev/ttyUSB0`.
