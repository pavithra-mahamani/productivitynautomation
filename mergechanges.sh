#!/bin/bash
###########################################################
# Description: Helper script to merge the Py2 to Py3 repos
#
###########################################################
NUM_DAYS=58
SRC=/Users/jagadeshmunta/py3porting/merging/py2/testrunner
DEST=/Users/jagadeshmunta/py3porting/merging/testrunner
MERGE_CHANGES=../merge_manually.txt
FILE=../whatchanged_since_june19_aug16_${NUM_DAYS}days.txt
TO_COPY=../files_to_copy.txt
TO_MERGE=../py_files_to_merge.txt
PWD=`pwd`
cd $SRC
echo 'git whatchanged --since='"'$NUM_DAYS days ago'"' -p'
git whatchanged --since="$NUM_DAYS days ago" -p > $PWD/$FILE
cd $PWD
echo "egrep '\--- /dev' $FILE -A 1 |egrep 'b' |cut -f2- -d'/' "
egrep '\--- /dev' $FILE -A 1 |egrep 'b' |cut -f2- -d'/'  > $TO_COPY
echo "egrep '\---' $FILE |egrep -v '/dev' |egrep -v '\.py' |egrep 'a' |cut -f2- -d'/'"
egrep '\---' $FILE |egrep -v '/dev' |egrep -v '\.py' |egrep 'a' |cut -f2- -d'/' >> $TO_COPY
egrep '\---' $FILE |egrep -v '/dev' |egrep '\.py' |egrep 'a' |cut -f2- -d'/' > $TO_MERGE

echo Changes: Check $FILE $TO_COPY $TO_MERGE
echo "Press enter or ctrl+c"
read x

echo "Copying files..."
for F in `cat $TO_COPY`
do
   D=`dirname $F`
   if [ ! -d $DEST/$D ]; then
      mkdir -p $DEST/$D
   fi
   if [ ! -f $DEST/$F ]; then
      echo NEW:$F
   else
      echo OLD:$F
   fi
   echo cp -r $SRC/$F $DEST/$F
   cp -r $SRC/$F $DEST/$F
done

echo "*** TO be merged ****"
echo "">$MERGE_CHANGES
TO_BE_MERGED=../to_be_conv_py3
if [ -d $TO_BE_MERGED ]; then
  rm -rf $TO_BE_MERGED/*
fi
for F in `cat $TO_MERGE`
do
  D=`dirname $F`
  if [ ! -d $TO_BE_MERGED/$D ]; then
     mkdir -p $TO_BE_MERGED/$D
  fi
  cp $SRC/$F $TO_BE_MERGED/$F
  2to3 -f all -f buffer -f idioms -f set_literal -f ws_comma -w -n $TO_BE_MERGED/$F
  echo diff $TO_BE_MERGED/$F $DEST/$F >>$MERGE_CHANGES
  diff $TO_BE_MERGED/$F $DEST/$F >>$MERGE_CHANGES
done

echo "Check $MERGE_CHANGES to do manual merge."
