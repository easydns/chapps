#!/usr/bin/bash

sender=$1
while read line
  do eval echo "$line"
done < ${2:-"test_message.txt"} | nc localhost 25
