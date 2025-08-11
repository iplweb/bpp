#!/bin/sh
set -euo pipefail

dropdb -f test_bpp

for a in test_bpp_gw{0,1,2,3,4,5,6,7,8,9,10};
do dropdb -f $a;
done
