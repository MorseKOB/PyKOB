# MRT Selector Specification File Format

Using a hardware selector device with MRT (using the `--selector` option) requires
a 'mrtsel' selector specification file to control how MRT operates for each
selection. This document describes the format used.

There is an example spec file included: mrt_sel_spec.mrtsel.example

## JSON Format

The specification file is a JSON format file, as used by JavaScript, Python, and
many other programming languages. Familiarity with JSON can be helpful, but is
not required to be able to create or modify a specification file to meet your
needs. It is suggested that you start with the example file, as that will give
you everything you need, and you should be able to simply modify some of the
content.

### File is JSON Format Map/Dictionary

The top entries are:

* "type": It can have a value of:
    a. "1OF4" - Hardware that selects 1 of 4 options
    b. "BINARY" - Hardware that uses the 4 handshake signals to select 0-15 (1 of 16 options)
* "selections": This is an array/list with an entry for each possible selection
  * Each element of the array/list is a map/dictionary with two entries:
    a. "desc": The description of the selection. This is displayed in the terminal window when
       the selector is switched to that selection
    b. "args": The value is an array/list with the command line arguments that would be used
       when executing MRT (if you did it from the command line)

       Each argument is a string in quotes (even if it's a number like the 'wire'). Arguments
       are separated by a comma.

       The configuration environment used to run the main MRT is the base for the selections,
       so arguments specified are applied to it to run the selection. Therefore, only a wire,
       or possibly a wire and a few additional options might be all that is needed as the "args" value

       The elements are in order. The first is #1 (for a '1OF4' type), second is #2, etc.

       If there are fewer elements than needed (less than 4 or less than 16), the rest are defaulted
       to running MRT with the configuration of the parent (less the '--selector port spec', of course).

       The only restriction is that you cannot specify '--selector' in these arguments.
