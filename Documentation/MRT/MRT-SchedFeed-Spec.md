# MRT Scheduled Feed Specification File Format

Having MRT send code on a schedule (using the `--schedfeed sf_spec_file` option) requires
a 'mrtsfs' scheduled-feed specification file (sf_spec_file) to control when and what MRT sends.
This document describes the format used.

There is an example spec file included: mrt_schfd_example.mrtsfs

## JSON Format

The specification file is a JSON format file, as used by JavaScript, Python, and
many other programming languages. Familiarity with JSON can be helpful, but is
not required to be able to create or modify a specification file to meet your
needs. It is suggested that you start with the example file, as that will give
you everything you need, and you should be able to simply modify some of the
content.

### File is JSON Format Map/Dictionary

The top entry is:

* "specs": The value is a list of one or more specifications.

Each specification is a Map/Dictionary with the following keys:value

* *condition*:*time* The 'condition' is one of:

    1. "at" - Send AT this *time*, even if wire is busy (breaks in if needed). *time* = 24-Hour Local Time
    2. "at_ii" - AT this *time* IF the wire is IDLE. If not idle at this time the message is not sent (it is skipped). *time* = 24-Hour Local Time
    3. "when_i" - Send WHEN the line is IDLE, at/after this *time*. *time* = 24-Hour Local Time
    4. "idle" - Send if the line remains IDLE for a given *period of time*. *time* = Minutes of idle time

* 'msg':*message text* The (single) message to be sent when the *condition* is satisfied.
  * or

* 'msgs':*List of message texts* Two or more messages, from which one will be selected to send, randomly, when the condition is satisfied.

The *message text* is the message to be sent, just as you would enter it using the keyboard sender. Two special control sequences are supported within the text.

#### Message Text Control Sequences

Control sequences are in the form:
«*control*»

Where '«' is Unicode U+00AB (Left-double-angle-quote) and '»' is Unicode U+00BB (Right-double-angle-quote) and *control* is:

* **\$**_var_  : A `$` followed by the name of an environment variable. The value of the environment variable will be used in the text.
* **P**_seconds_  : Pause for *seconds* before continuing to send. The value of *seconds* can include fractional values (3.5 = Three and a half seconds)

Though not considered **Control Sequences**, the other two **Special** characters used within the message text are:

* **~**  : Open the key
* **+**  : Close the key

These must be included in the text unless you know that the key will be open when the message is to be sent, and/or you want to leave the key open after sending the message.

Note: JSON strings must be enclosed within quotes __"text"__ (not apostrophes __'text'__).

## Example

It is suggested that you refer to the `mrt_schfd_example.mrtsfs` file, as it is tested. However, for convenience, the following should help:

``` json
{
    "specs": [
        {
            "at":906,
            "msg":"~ «$OFFICE» ON +     ~ AR «$OFFICE» +"
        },
        {
            "at_ii":1207,
            "msg":"~ «$OFFICE» CHECKING IN= AR «$OFFICE» +"
        },
        {
            "when_i":1950,
            "msg":"~ «$OFFICE» DONE +     ~ 30 «$OFFICE» +"
        },
        {
            "idle":10,
            "msgs":[
                "~ I «$OFFICE» 37 SEEING WHO IS THERE. = 73 «$OFFICE» +",
                "~ I «$OFFICE» INVITING YOU TO JOIN IN. = K «$OFFICE» +",
                "~ I «$OFFICE» WELCOME TO OUR WIRE. = «P3.2» WE HOPE YOU ARE ENJOYING YOURSELF. K «$OFFICE» +",
                "~ I «$OFFICE» 77 PLEASE COME VISIT «$SITE_NAME» AND SEE US IN ACTION. = K «$OFFICE» +"
            ]
        }
    ]
}
```
