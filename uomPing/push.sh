#/bin/sh
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

CONTAINER=${DIR##*/}

#CONTAINERTAG=monroe/${CONTAINER}
CONTAINERTAG=vardalis/monroe-ping:original

docker login && docker tag ${CONTAINER} ${CONTAINERTAG} && docker push ${CONTAINERTAG} && echo "Finished uploading ${CONTAINERTAG}"
