#!/usr/bin/env bash
#
# Copyright (C) 2015-2016: Alignak team, see AUTHORS.txt file for contributors
#
# This file is part of Alignak Backend Import.
#
# Alignak Backend Importis free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Alignak Backend Importis distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Alignak Backend Import. If not, see <http://www.gnu.org/licenses/>.

# import the unit testing modules

set -e

THIS_PATH=$(dirname "$0")
BASE_PATH=$(dirname "$THIS_PATH")

cd $BASE_PATH

echo 'Upgrade pip ...'
pip install --upgrade pip

echo 'Installing application requirements ...'
pip install -r requirements.txt
echo 'Installing application in development mode ...'
pip install -e .
echo 'Installing tests requirements ...'
pip install --upgrade -r test_requirements.txt

pyversion=$(python -c "import sys; print(''.join(map(str, sys.version_info[:2])))")
if test -e "test_requirements.py${pyversion}.txt"
then
    pip install -r "test_requirements.py${pyversion}.txt"
fi

