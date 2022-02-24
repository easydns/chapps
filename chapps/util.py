"""chapps.util

These are the utility classes for CHAPPS
"""
from collections.abc import Mapping
import re
import logging, chapps.logging

logger = logging.getLogger( __name__ )
logger.setLevel( logging.DEBUG )

class AttrDict():
    """This simple class allows accessing the keys of a hash as attributes on an object.  As a useful side effect it also casts floats and integers in advance.  This object is used for holding the configuration data."""
    boolean_pattern = re.compile('^[Tt]rue|[Ff]alse$')
    def __init__(self, data={}):
        for k, v in data.items():
            if k[0:2] != '__':
                val = v
                try:
                    val = int(v)
                except ValueError:
                    try:
                        val = float(v)
                    except ValueError:
                        m = self.boolean_pattern.match(v)
                        if m:
                            val = (m.span(0)[1] == 4) # if the match is 4 chars long, it is True
                setattr(self, k, val)

class PostfixPolicyRequest(Mapping): # empty lines eliminated for paste-ability
    """An implementation of Mapping which by default only processes and caches values from the data payload when they are accessed, to avoid a bunch of useless parsing."""
    def __init__(self, payload):
        """We get passed a payload of strings which are formatted as 'key=val'"""
        self._payload = payload[0:-2]
    ### the main reason for this class: find and memoize as attributes the values in the request payload
    def __getattr__(self, attr, dfl=None):
        """Overload in order to search for missing attributes in the payload"""
        ### TODO: restore the logic below
        line = next(( l for l in self._payload if attr == l.split('=')[0] ), None)
        if line:
            key, value = line.split("=")
            setattr(self, key, value)
            return value
        else:
            logger.debug(f"No lines in {self} matched {attr}.")
        return None
    ### Since the datastructure can function as a hash, provide optimization
    def __getitem__(self, key):
        """Getting an item should optimize the result via the attribute mechanism"""
        return getattr(self, key)
    ### The datastructure is iterable, in case we need to enumerate the request
    def __iter__(self):
        """Return an iterable representing the mapping"""
        if not getattr(self, '_mapping', None):
            self._mapping = { k: v for k,v in [ l.split("=") for l in self._payload ] }
            # Since we end up parsing the entire payload, optimize it for future random access
            for k, v in self._mapping.items():
                setattr(self, k, v)
        yield from self._mapping
    ### The length of the PPR is considered to be the number of items stored
    def __len__(self):
        """Act like a dict and return the number of k,v pairs"""
        return len(self._payload)
    ### Representations of PPR use their own class name, and otherwise dump the payload, but not a list of attributes
    def __repr__(self):
        """Dump the data in _payload"""
        return "%s( %r )" % ( self.__class__.__name__, self._payload )
    ### In order to use memoization with PPRs, a hash function is required
    def __hash__(self):
        """Create a reliable hash for this PPR"""
        if '_hash' not in vars(self):
            self._hash = hash( f"{self.instance}:{self.queue_id}" )
        return self._hash
    ### This convenience property provides a list of recipient email addresses, since the line may contain more than one
    @property
    def recipients(self):
        """A convenience method to split the 'recipient' datum into comma-separated tokens, for easier counting."""
        if not self._recipients:
            self._recipients = self.recipient.split(',') if self.recipient and len(self.recipient) > 0 else []
        return self._recipients
