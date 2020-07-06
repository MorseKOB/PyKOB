# Release notes

## MorseKOB 4.1.0 (relative to MorseKOB 2.5)

These notes need to be fleshed out before MKOB is released.

### What's new

- code reader adapts to actual speed of received Morse
- can handle International Code

### What's missing

- can't use Escape key to regain control of the wire
- no Preferences screen for setting options (have to use Configure utility for now)
- no support (yet) for sounder driver interface

### What's different

- have to type ~ to open the wire when sending from the keyboard and + to close it
- missing packets are indicated by a double underscore instead of an asterisk; long pauses also

### Known issues

- keyboard sender shortens spaces longer than 3 seconds to 0.5 seconds
