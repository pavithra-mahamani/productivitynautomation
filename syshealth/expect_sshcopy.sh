#!/usr/bin/expect -f
#
# Install RSA SSH KEY with no passphrase
#

set user [lindex $argv 0]
set password [lindex $argv 1]
set host [lindex $argv 2]
spawn ssh-copy-id $user@$host

expect {
    "*password:" { send "$password\n"; }
}
