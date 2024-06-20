# About this helm chart and gitlab as DATAPlant DataHub #

This helm chart is build according to the official documentation to [install gitlab on kubernetes](https://docs.gitlab.com/charts/).
Unfortunately this approach cannot be used to install gitlab as DATAPlant DataHub, because DATAPlant only offers a modified gitlab image suited for the [docker installation of gitlab](https://docs.gitlab.com/ee/install/docker.html).

So the conclusion is to install the DATAPlant-provided image on kubernetes. This is not possible using the current helm chart (which is build on top of the official gitlab helm chart). Thus we need an additional, non-official helm chart to install the DataHub: `fairagro-datahub`.
