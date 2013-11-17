# -*- coding: utf-8 -*-
# Natural Language Toolkit: Brill Tagger
#
# Copyright (C) 2001-2013 NLTK Project
# Authors: Christopher Maloof <cjmaloof@gradient.cis.upenn.edu>
#          Edward Loper <edloper@gmail.com>
#          Steven Bird <stevenbird1@gmail.com>
#          Marcus Uneson <marcus.uneson@gmail.com>
# URL: <http://nltk.org/>
# For license information, see  LICENSE.TXT

from __future__ import print_function
import yaml
import itertools as it


class BrillTemplateI(object):
    """
    An interface for generating lists of transformational rules that
    apply at given sentence positions.  ``BrillTemplateI`` is used by
    ``Brill`` training algorithms to generate candidate rules.
    """
    def __init__(self):
        raise NotImplementedError()

    def applicable_rules(self, tokens, i, correctTag):
        """
        Return a list of the transformational rules that would correct
        the *i*th subtoken's tag in the given token.  In particular,
        return a list of zero or more rules that would change
        *tokens*[i][1] to *correctTag*, if applied to *token*[i].

        If the *i*th token already has the correct tag (i.e., if
        tagged_tokens[i][1] == correctTag), then
        ``applicable_rules()`` should return the empty list.

        :param tokens: The tagged tokens being tagged.
        :type tokens: list(tuple)
        :param i: The index of the token whose tag should be corrected.
        :type i: int
        :param correctTag: The correct tag for the *i*th token.
        :type correctTag: any
        :rtype: list(BrillRule)
        """
        raise NotImplementedError()

    def get_neighborhood(self, token, index):
        """
        Returns the set of indices *i* such that
        ``applicable_rules(token, i, ...)`` depends on the value of
        the *index*th token of *token*.

        This method is used by the "fast" Brill tagger trainer.

        :param token: The tokens being tagged.
        :type token: list(tuple)
        :param index: The index whose neighborhood should be returned.
        :type index: int
        :rtype: set
        """
        raise NotImplementedError()


from nltk.tag.brill.rule import Rule


class Template(BrillTemplateI):
    """
    A brill Template that generates a list of L{Rule}s that apply at a given sentence
    position.  In particular, each C{Template} is parameterized by a list of
    independent features (a combination of a specific
    property to extract and a list C{L} of relative positions at which to extract
    it) and generates all Rules that:

      - use the given features, each at its own independent position; and
      - are applicable to the given token.
    """
    ALLTEMPLATES = []
    #record a unique id of form "001", for each template created
#    _ids = it.count(0)

    def __init__(self, *features):
        """
        Construct a Template for generating Rules.

        Takes a list of Features. A C{Feature} is a combination
        of a specific property and its relative positions and should be
        a subclass of L{nltk.tag.brill.template.Feature}.

        An alternative calling convention (kept for backwards compatibility,
        but less expressive as it only permits one feature type) is
        Template(Feature, (start1, end1), (start2, end2), ...)
        In new code, that would be better written
        Template(Feature(start1, end1), Feature(start2, end2), ...)

        :type features: list of Features
        :param features: the features to build this Template on
        """

        #determine the calling form: either
        #Template(Feature, args1, [args2, ...)]
        #Template(Feature1(args),  Feature2(args), ...)
        if all(isinstance(f, Feature) for f in features):
            self._features = features
        elif issubclass(features[0], Feature) and all(isinstance(a, tuple) for a in features[1:]):
            self._features = [features[0](*tp) for tp in features[1:]]
        else:
            raise TypeError(
                "expected either Feature1(args), Feature2(args), ... or Feature, (start1, end1), (start2, end2), ...")
        self.id = "{0:03d}".format(len(self.ALLTEMPLATES))
        self.ALLTEMPLATES.append(self)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, ",".join([str(f) for f in self._features]))

    def applicable_rules(self, tokens, index, correct_tag):
        if tokens[index][1] == correct_tag:
            return []

        # For each of this Template's features, find the conditions
        # that are applicable for the given token.
        # Then, generate one Rule for each combination of features
        # (the crossproduct of the conditions).

        applicable_conditions = self._applicable_conditions(tokens, index)
        xs = list(it.product(*applicable_conditions))
        return [Rule(self.id, tokens[index][1], correct_tag, tuple(x)) for x in xs]

    def _applicable_conditions(self, tokens, index):
        """
        :returns: A set of all conditions for rules
        that are applicable to C{tokens[index]}.
        """
        conditions = []

        for feature in self._features:
            conditions.append([])
            for pos in feature.positions:
                if not (0 <= index+pos < len(tokens)):
                    continue
                value = feature.extract_property(tokens, index+pos)
                conditions[-1].append( (feature, value) )
        return conditions

    def get_neighborhood(self, tokens, index):
        # inherit docs from BrillTemplateI

        # applicable_rules(tokens, index, ...) depends on index.
        neighborhood = set([index])  #set literal for python 2.7+

        # applicable_rules(tokens, i, ...) depends on index if
        # i+start < index <= i+end.

        allpositions = [0] + [p for feat in self._features for p in feat.positions]
        start, end = min(allpositions), max(allpositions)
        s = max(0, index+(-end))
        e = min(index+(-start)+1, len(tokens))
        for i in range(s, e):
            neighborhood.add(i)
        return neighborhood

    @classmethod
    def expand(cls, featurelists, combinations=None, skipintersecting=True):
        """
        Factory method to mass generate Templates from a list L of Feature lists,
        by computing the Cartesian product of all non-empty subsets of L,
        and removing any duplicates. The feature lists may have been specified
        manually, but perhaps generated from Feature.expand(). For instance,


          Template.expand([ [Word([0]), Word([0,1])], [Pos([-2]), Pos([-1])] ])

          will return a list of eight templates
              Template(Word([0])),
              Template(Word([0, 1])),
              Template(Pos([-2])),
              Template(Pos([-1])),
              Template(Pos([-2]),Word([0])),
              Template(Pos([-1]),Word([0])),
              Template(Pos([-2]),Word([0, 1])),
              Template(Pos([-1]),Word([0, 1]))]

        With propersubsets=False, L itself rather than all its subsets will be used,
        so that each featurelist in L is represented in all templates in the output
        (in the example, only the four last templates would be output).

        Templates where one feature is a subset of another, such as
        Template(Word([0,1]), Word([1]), will not appear in the output.
        By default, this non-subset constraint is tightened to disjointness:
        Templates of type Template(Word([0,1]), Word([1,2]) will also be filtered out.
        With skipintersecting=False, then such Templates are allowed

        WARNING: this method makes it very easy to fill all your memory when training
        generated templates on any real-world corpus

        :param featurelists: lists of Features, whose Cartesian product will return a set of Templates
        :type featurelists: list of (list of Features)
        :param combinations: given n featurelists: if combinations=k, all generated Templates will have
                k features; if combinations=(k1,k2) they will have k1..k2 features; if None, defaults to 1..n
        :type combinations: None, int, or (int, int)
        :param skipintersecting: if True, do not output intersecting Templates (non-disjoint positions for some feature)
        :type skipintersecting: bool
        :returns: generator of Templates

        """

        def nonempty_powerset(xs): #xs is a list
            #itertools docnonempty_powerset([1,2,3]) --> (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)

            #find the correct tuple given combinations, one of {None, k, (k1,k2)}
            k = combinations #for brevity
            combrange = ((1, len(xs)+1) if k is None else     #n over 1 .. n over n (all non-empty combinations)
                         (k, k+1) if isinstance(k, int) else  #n over k (only
                         (k[0], k[1]+1))                      #n over k1, n over k1+1... n over k2
            return it.chain.from_iterable(it.combinations(xs, r)
                                          for r in range(*combrange))
        seentemplates = set()
        for picks in nonempty_powerset(featurelists):
            for pick in it.product(*picks):
                if any(i != j and x.issuperset(y)
                       for (i, x) in enumerate(pick)
                       for (j,y) in enumerate(pick)):
                    continue
                if skipintersecting and any(i != j and x.intersects(y)
                                            for (i, x) in enumerate(pick)
                                            for (j, y) in enumerate(pick)):
                    continue
                thistemplate = cls(*sorted(pick))
                strpick = str(thistemplate)
                if strpick in seentemplates: #already added
                    cls.poptemplate()
                    continue
                seentemplates.add(strpick)
                yield thistemplate

    @classmethod
    def poptemplate(cls):
        return cls.ALLTEMPLATES.pop() if cls.ALLTEMPLATES else None



class Feature(yaml.YAMLObject):
    """
    An abstract base class for Features. A Feature is a combination of
    a specific property-computing method and a list of relative positions
    to apply that method to.

    The property-computing method, M{extract_property(tokens, index)},
    must be implemented by every subclass. It extracts or computes a specific
    property for the token at the current index. Typical extract_property()
    methods return features such as the token text or tag; but more involved
    methods may consider the entire sequence M{tokens} and
    for instance compute the length of the sentence the token belongs to.

    In addition, the subclass may have a PROPERTY_NAME, which is how
    it will be printed (in Rules and Templates, etc). If not given, defaults
    to the classname.

    The subclass may also explicitly set a tag for yaml serialization. If
    not given, defaults to '!' + the classname in lowercase (e.g., "!tag").

    """
    yaml_tag = None
    PROPERTY_NAME = None


    def __init__(self, positions, end=None):
        """
        Construct a Feature which may apply at C{positions}.

        :type positions: list of int
        :param positions: the positions at which this features should apply
        :raises ValueError: illegal position specifications

        An alternative calling convention, for contiguous positions only,
        is Feature(start, end):

        :type start: int
        :param start: start of range where this feature should apply
        :type end: int
        :param end: end of range (NOTE: inclusive!) where this feature should apply

        """
        self.positions = None #to avoid warnings
        if end is None:
            self.positions = tuple(sorted(set([int(i) for i in positions])))
        else:                #positions was actually not a list, but only the start index
            try:
                if positions > end:
                    raise TypeError()
                self.positions = tuple(range(positions, end+1))
            except TypeError:
                #let any kind of erroneous spec raise ValueError
                raise ValueError("illegal interval specification: (start={0}, end={1})".format(positions, end))

        #set property name given in subclass, or otherwise name of subclass
        self.PROPERTY_NAME = self.__class__.PROPERTY_NAME or self.__class__.__name__
        #set yaml_tag name given in subclass, or otherwise name of subclass, lowercased
        self.yaml_tag = self.__class__.yaml_tag or "!{0}".format(self.__class__.__name__.lower())

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__, list(self.positions))

    @classmethod
    def expand(cls, starts, winlens, excludezero=False):
        """
        Return a list of features, one for each start point in starts
        and for each window length in winlen. If excludezero is True,
        no Features containing 0 in its positions will be generated
        (many tbl trainers have a special representation for the
        target feature at [0])

        :param starts: where to start looking for Feature
        :type starts: list of ints
        :param winlens: window lengths where to look for Feature
        :type starts: list of ints
        :param excludezero: do not output any Feature with 0 in any of its positions.
        :type excludezero: bool
        :returns: list of Features
        :raises ValueError: for non-positive window lengths
        """
        if not all(x > 0 for x in winlens):
            raise ValueError("non-positive window length in {0:s}".format(winlens))
        xs = (starts[i:i+w] for w in winlens for i in range(len(starts)-w+1))
        return [cls(x) for x in xs if not (excludezero and 0 in x)]

    def issuperset(self, other):
        return (self.__class__ is other.__class__ and
               set(self.positions) >= set(other.positions))

    def intersects(self, other):
        return (self.__class__ is other.__class__ and
               set(self.positions) & set(other.positions))

    #Rich comparisons for Features. With @functools.total_ordering (Python 2.7+),
    # it will be enough to define __lt__ and __eq__
    def __eq__(self, other):
        return (self.__class__ is other.__class__ and
               self.positions == other.positions)
    def __lt__(self, other):
        return (self.__class__.__name__ < other.__class__.__name__ or
               #self.positions is a sorted tuple of ints
               self.positions < other.positions)
    def __ne__(self, other):
        return not (self == other)
    def __gt__(self, other):
        return other < self
    def __ge__(self, other):
        return not self < other
    def __le__(self, other):
        return self < other or self == other

    @staticmethod
    def extract_property(tokens, index):
        raise NotImplementedError("subclass of Feature must define extract_property(tokens, index)")


