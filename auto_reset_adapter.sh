#! /bin/bash
date=`date "+%Y-%m-%d %H:%M"`
numsensors=$(<numsensors.txt)
if [ "$numsensors" -lt 1 ]; then
  echo $date '# ERROR: ' only $numsensors sensors found
  hciconfig hci0 reset
else
  echo $date '+ OK: ' $numsensors sensors found
fi

