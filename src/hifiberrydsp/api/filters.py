import json
import math
import numpy as np
import cmath

from hifiberrydsp.filtering.biquad import Biquad

class Filter:
    def __init__(self, **kwargs):
        self.params = kwargs
        self.type = kwargs.get('type', None)

    def toJSON(self):
        return json.dumps(self.params)

    @staticmethod
    def normalize_biquad(b0, b1, b2, a0, a1, a2):
        """
        Normalize biquad coefficients by dividing all coefficients by a0
        to ensure a0 equals 1.0
        
        Args:
            b0, b1, b2: Numerator coefficients
            a0, a1, a2: Denominator coefficients
            
        Returns:
            Tuple of normalized coefficients (b0, b1, b2, 1.0, a1', a2')
        """
        # Return early if a0 is already 1 or close to it
        if abs(a0 - 1.0) < 1e-10:
            return (b0, b1, b2, a0, a1, a2)
            
        # Prevent division by zero
        if abs(a0) < 1e-10:
            raise ValueError("Cannot normalize biquad: a0 is too close to zero")
            
        # Normalize coefficients by dividing by a0
        return (b0/a0, b1/a0, b2/a0, 1.0, a1/a0, a2/a0)

    def biquadCoefficients(self, fs):
        """
        Return biquad coefficients for the filter.
        Subclasses should implement this, but default implementation
        uses the internal Biquad object if available.
        """
        if hasattr(self, '_biquad'):
            coeffs = self._biquad.coefficients_b_a(a0=True)
            return coeffs
        raise NotImplementedError("Subclasses must implement this method")

    def frequencyResponse(self, f, fs):
        """
        Calculate the complex frequency response of the filter at a specific frequency
        
        Args:
            f: Frequency in Hz
            fs: Sample rate in Hz
            
        Returns:
            Complex number representing the filter response at frequency f
        """
        # Get biquad coefficients for the filter
        try:
            coeffs = self.biquadCoefficients(fs)
            if not coeffs:
                return complex(1, 0)  # Neutral response if no coefficients
                
            # Extract coefficients: [b0, b1, b2, a0, a1, a2]
            b0, b1, b2, a0, a1, a2 = coeffs
            
            # Use normalized coefficients for calculation
            b0, b1, b2, a0, a1, a2 = Filter.normalize_biquad(b0, b1, b2, a0, a1, a2)
            
            # Calculate z = e^(j*omega*T)
            omega = 2 * math.pi * f / fs
            z = cmath.rect(1, -omega)  # z^-1
            z2 = z * z  # z^-2
            
            # Calculate H(z) = (b0 + b1*z^-1 + b2*z^-2) / (1 + a1*z^-1 + a2*z^-2)
            # Since a0 = 1 after normalization, we can simplify the calculation
            numerator = b0 + b1 * z + b2 * z2
            denominator = 1 + a1 * z + a2 * z2
            
            return numerator / denominator
            
        except NotImplementedError:
            # Default to neutral response if not implemented
            return complex(1, 0)

    def frequencyResponseDb(self, f, fs):
        """
        Calculate the frequency response in decibels at a specific frequency
        
        Args:
            f: Frequency in Hz
            fs: Sample rate in Hz
            
        Returns:
            Amplitude response in decibels
        """
        response = self.frequencyResponse(f, fs)
        magnitude = abs(response)
        
        # Convert to decibels, handling edge case
        if magnitude > 0:
            return 20 * math.log10(magnitude)
        else:
            return -120  # Very small value in dB for zero magnitude
    
    @staticmethod
    def getFrequencyResponse(fs, filters, frequencies=None):
        """
        Calculate the combined frequency response of a chain of filters
        
        Args:
            fs: Sample rate in Hz
            filters: List of Filter objects
            frequencies: List of frequencies in Hz (optional)
                        If not provided, uses logarithmic scale from 20Hz to 20kHz
                        
        Returns:
            Dictionary with 'frequencies' and 'response' keys
        """
        # Generate default frequencies if not provided
        if frequencies is None:
            frequencies = Filter.logspace_frequencies(20, 20000, 8)
        
        # Initialize the response array with zeros (0 dB is neutral)
        response = np.zeros(len(frequencies))
        
        # Calculate the combined response at each frequency
        for filter_obj in filters:
            for i, freq in enumerate(frequencies):
                response[i] += filter_obj.frequencyResponseDb(freq, fs)
        
        return {
            'frequencies': frequencies,
            'response': response.tolist()
        }
    
    @staticmethod
    def logspace_frequencies(fmin, fmax, points_per_octave):
        """
        Generate logarithmically spaced frequencies
        
        Args:
            fmin: Minimum frequency in Hz
            fmax: Maximum frequency in Hz
            points_per_octave: Number of points per octave
            
        Returns:
            List of frequencies in Hz
        """
        # Calculate number of octaves
        num_octaves = math.log2(fmax / fmin)
        
        # Calculate total number of points
        num_points = int(points_per_octave * num_octaves) + 1
        
        # Generate log-spaced points
        frequencies = []
        for i in range(num_points):
            # Calculate frequency using logarithmic spacing
            exponent = i / points_per_octave
            freq = fmin * (2 ** exponent)
            
            # Make sure we don't exceed fmax
            if freq <= fmax:
                frequencies.append(freq)
            else:
                break
        
        # Make sure fmax is included
        if frequencies[-1] < fmax:
            frequencies.append(fmax)
            
        return frequencies

    @staticmethod
    def fromJSON(json_string):
        data = json.loads(json_string)
        filter_type = data.get("type")
        if filter_type == "PeakingEq":
            return PeakingEq(**data)
        elif filter_type == "LowPass":
            return LowPass(**data)
        elif filter_type == "HighPass":
            return HighPass(**data)
        elif filter_type == "LowShelf":
            return LowShelf(**data)
        elif filter_type == "HighShelf":
            return HighShelf(**data)
        elif filter_type == "Volume":
            return Volume(**data)
        elif filter_type == "GenericBiquad":
            return GenericBiquad(**data)
        else:
            raise ValueError(f"Unknown filter type: {filter_type}")

class PeakingEq(Filter):
    def __init__(self, f, db, q, **kwargs):
        kwargs['type'] = 'PeakingEq'
        super().__init__(f=f, db=db, q=q, **kwargs)
        self.f = f
        self.db = db
        self.q = q
        
    def biquadCoefficients(self, fs):
        # Create Biquad object for the filter if not already created
        if not hasattr(self, '_biquad'):
            self._biquad = Biquad.peaking_eq(self.f, self.q, self.db, fs)
        return self._biquad.coefficients_b_a(a0=True)

class LowPass(Filter):
    def __init__(self, f, db, q, **kwargs):
        kwargs['type'] = 'LowPass'
        super().__init__(f=f, db=db, q=q, **kwargs)
        self.f = f
        self.db = db
        self.q = q
        
    def biquadCoefficients(self, fs):
        if not hasattr(self, '_biquad'):
            self._biquad = Biquad.low_pass(self.f, self.q, fs)
        return self._biquad.coefficients_b_a(a0=True)

class HighPass(Filter):
    def __init__(self, f, db, q, **kwargs):
        kwargs['type'] = 'HighPass'
        super().__init__(f=f, db=db, q=q, **kwargs)
        self.f = f
        self.db = db
        self.q = q
        
    def biquadCoefficients(self, fs):
        if not hasattr(self, '_biquad'):
            self._biquad = Biquad.high_pass(self.f, self.q, fs)
        return self._biquad.coefficients_b_a(a0=True)

class LowShelf(Filter):
    def __init__(self, f, db, slope, gain, **kwargs):
        kwargs['type'] = 'LowShelf'
        super().__init__(f=f, db=db, slope=slope, gain=gain, **kwargs)
        self.f = f
        self.db = db
        self.slope = slope
        self.gain = gain
        
    def biquadCoefficients(self, fs):
        if not hasattr(self, '_biquad'):
            # The Biquad.low_shelf uses db gain directly, pass gain as db
            self._biquad = Biquad.low_shelf(self.f, self.slope, self.gain, fs)
        return self._biquad.coefficients_b_a(a0=True)

class HighShelf(Filter):
    def __init__(self, f, db, slope, gain, **kwargs):
        kwargs['type'] = 'HighShelf'
        super().__init__(f=f, db=db, slope=slope, gain=gain, **kwargs)
        self.f = f
        self.db = db
        self.slope = slope
        self.gain = gain
        
    def biquadCoefficients(self, fs):
        if not hasattr(self, '_biquad'):
            # The Biquad.high_shelf uses db gain directly, pass gain as db
            self._biquad = Biquad.high_shelf(self.f, self.slope, self.gain, fs)
        return self._biquad.coefficients_b_a(a0=True)

class Volume(Filter):
    def __init__(self, db, **kwargs):
        kwargs['type'] = 'Volume'
        super().__init__(db=db, **kwargs)
        self.db = db
        
    def biquadCoefficients(self, fs):
        if not hasattr(self, '_biquad'):
            self._biquad = Biquad.volume(self.db)
        return self._biquad.coefficients_b_a(a0=True)

class GenericBiquad(Filter):
    def __init__(self, a0=1.0, a1=0.0, a2=0.0, b0=1.0, b1=0.0, b2=0.0, fs=48000, **kwargs):
        kwargs['type'] = 'GenericBiquad'
        super().__init__(a0=a0, a1=a1, a2=a2, b0=b0, b1=b1, b2=b2, fs=fs, **kwargs)
        self.a0 = a0
        self.a1 = a1
        self.a2 = a2
        self.b0 = b0
        self.b1 = b1
        self.b2 = b2
        self.fs = fs
        
    def biquadCoefficients(self, fs):
        # Return the coefficients directly if sample rate matches
        if fs == self.fs:
            return [self.b0, self.b1, self.b2, self.a0, self.a1, self.a2]
        
        # Apply frequency warping if the requested sample rate is different
        # from the sample rate the filter was designed for
        k = math.tan(math.pi * 0.5 * self.fs / fs) / math.tan(math.pi * 0.5)
        
        # Apply the warping to the coefficients
        # Formula based on bilinear transform frequency warping
        b0_w = self.b0
        b1_w = self.b1 * k
        b2_w = self.b2 * k * k
        a0_w = self.a0
        a1_w = self.a1 * k
        a2_w = self.a2 * k * k
        
        # Return the warped coefficients
        return [b0_w, b1_w, b2_w, a0_w, a1_w, a2_w]
    
    @classmethod
    def from_biquad(cls, biquad, fs=48000):
        """
        Create a GenericBiquad from a Biquad object
        
        Args:
            biquad: Biquad object to convert
            fs: Sample rate in Hz that filter was designed for, default 48000
        """
        return cls(
            a0=biquad.a0,
            a1=biquad.a1,
            a2=biquad.a2,
            b0=biquad.b0,
            b1=biquad.b1,
            b2=biquad.b2,
            fs=fs
        )
