IIR filter format
=================

Standard IIR filters like high-pass, low-pass, bandpass and parametric 
equalisers can be described by a simple text syntax. This allows to 
create these filters from a textual respresentation that can be edited 
easyly without the need to use SigmaStudio to to filter adjustments 

* lp:frequency:q
  defines a second-order low-pass filter with the given corner frequency
  and quality. If quality isn't given, 0.707 is used (Butterworth filter)
* hp:frequency:q
  defines a second-order high-pass filter with the given corner frequency
  and quality. If quality isn't given, 0.707 is used (Butterworth filter)
* eq:frequency:q:gain
  defines a parametric equaliser with the given center frequency
  and quality. gain (in decibel) can be positive or negative
  
Often IIR filters can be chained to define more complex filters. To chain 
filters, just create a filter list of multiple filters seperated by ",",
e.g.

lp:1500Hz, lp:1500Hz, hp:300Hz:0.6, eq:1200Hz:2:+3dB

This defines a filter that consists of:
 - a 4th order low-pass at 1.5kHz (created from two 2nd order filters)
 - a 2nd order high-pass as 300Hz with a quality of 0.6
 - a parametric equaliser at 1.2kHz with a quality of 2.0 and +3dB gain  

