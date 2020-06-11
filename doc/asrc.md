# Usage of ASRCSs

The ADAU14xx models wer'e using on the DAC+ DSP, Beocreate 4CA and the DSP add-on board provide 8 asynchrounous sample rate converter 
that can be used to convert external I2S signals to the internal sample rate of the DSP or vice-versa.

While you're completely free how to use these, this is how we do it:

|ASRC|channels|usage|
|---|---|---|
|0|0,1|Raspberry Pi audio input|
|1|2,3|Analog audio input|
|2|||
|3|||
|4|8,9|DSP channel 4,5 output|
|5|10,11|DSP channel 2,3 output|
|6|12,13|DSP channel 0,1 output|
|7|14,15|SPDIF input|

We try to keep this consistent on different profiles. However, not every profile might use all of these
