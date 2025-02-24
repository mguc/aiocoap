# This file is part of the Python aiocoap library project.
#
# Copyright (c) 2012-2014 Maciej Wasilak <http://sixpinetrees.blogspot.com/>,
#               2013-2014 Christian Amsüss <c.amsuess@energyharvesting.at>
#
# aiocoap is free software, this file is published under the MIT license as
# described in the accompanying LICENSE file.

"""This module provides interface base classes to various aiocoap software
components, especially with respect to request and response handling. It
describes `abstract base classes`_ for messages, endpoints etc.

It is *completely unrelated* to the concept of "network interfaces".

.. _`abstract base classes`: https://docs.python.org/3/library/abc"""

from __future__ import annotations

import abc
from aiocoap.numbers.constants import DEFAULT_BLOCK_SIZE_EXP
from aiocoap.plumbingrequest import PlumbingRequest

from typing import Optional, Callable

class MessageInterface(metaclass=abc.ABCMeta):
    """A MessageInterface is an object that can exchange addressed messages over
    unreliable transports. Implementations send and receive messages with
    message type and message ID, and are driven by a Context that deals with
    retransmission.

    Usually, an MessageInterface refers to something like a local socket, and
    send messages to different remote endpoints depending on the message's
    addresses. Just as well, a MessageInterface can be useful for one single
    address only, or use various local addresses depending on the remote
    address.
    """

    @abc.abstractmethod
    async def shutdown(self):
        """Deactivate the complete transport, usually irrevertably. When the
        coroutine returns, the object must have made sure that it can be
        destructed by means of ref-counting or a garbage collector run."""

    @abc.abstractmethod
    def send(self, message):
        """Send a given :class:`Message` object"""

    @abc.abstractmethod
    async def determine_remote(self, message):
        """Return a value suitable for the message's remote property based on
        its .opt.uri_host or .unresolved_remote.

        May return None, which indicates that the MessageInterface can not
        transport the message (typically because it is of the wrong scheme)."""

class EndpointAddress(metaclass=abc.ABCMeta):
    """An address that is suitable for routing through the application to a
    remote endpoint.

    Depending on the MessageInterface implementation used, an EndpointAddress
    property of a message can mean the message is exchanged "with
    [2001:db8::2:1]:5683, while my local address was [2001:db8:1::1]:5683"
    (typical of UDP6), "over the connected <Socket at
    0x1234>, whereever that's connected to" (simple6 or TCP) or "with
    participant 0x01 of the OSCAP key 0x..., routed over <another
    EndpointAddress>".

    EndpointAddresses are only concstructed by MessageInterface objects,
    either for incoming messages or when populating a message's .remote in
    :meth:`MessageInterface.determine_remote`.

    There is no requirement that those address are always identical for a given
    address. However, incoming addresses must be hashable and hash-compare
    identically to requests from the same context. The "same context", for the
    purpose of EndpointAddresses, means that the message must be eligible for
    request/response, blockwise (de)composition and observations. (For example,
    in a DTLS context, the hash must change between epochs due to RFC7252
    Section 9.1.2).

    So far, it is required that hash-identical objects also compare the same.
    That requirement might go away in future to allow equality to reflect finer
    details that are not hashed. (The only property that is currently known not
    to be hashed is the local address in UDP6, because that is *unknown* in
    initially sent packages, and thus disregarded for comparison but needed to
    round-trip through responses.)
    """

    @property
    @abc.abstractmethod
    def hostinfo(self):
        """The authority component of URIs that this endpoint represents when
        request are sent to it

        Note that the presence of a hostinfo does not necessarily mean that
        globally meaningful or even syntactically valid URI can be constructed
        out of it; use the :attr:`.uri` property for this."""

    @property
    @abc.abstractmethod
    def hostinfo_local(self):
        """The authority component of URIs that this endpoint represents when
        requests are sent from it.

        As with :attr:`.hostinfo`, this does not necessarily produce sufficient
        input for a URI; use :attr:`.uri_local` instead."""

    @property
    def uri(self):
        """Deprecated alias for uri_base"""
        return self.uri_base

    @property
    @abc.abstractmethod
    def uri_base(self):
        """The base URI for the peer (typically scheme plus .hostinfo).

        This raises :class:`.error.AnonymousHost` when executed on an address
        whose peer coordinates can not be expressed meaningfully in a URI."""

    @property
    @abc.abstractmethod
    def uri_base_local(self):
        """The base URI for the local side of this remote.

        This raises :class:`.error.AnonymousHost` when executed on an address
        whose local coordinates can not be expressed meaningfully in a URI."""

    @property
    @abc.abstractmethod
    def is_multicast(self):
        """True if the remote address is a multicast address, otherwise false."""

    @property
    @abc.abstractmethod
    def is_multicast_locally(self):
        """True if the local address is a multicast address, otherwise false."""

    @property
    @abc.abstractmethod
    def scheme(Self):
        """The that is used with addresses of this kind

        This is usually a class property. It is applicable to both sides of the
        communication. (Should there ever be a scheme that addresses the
        participants differently, a scheme_local will be added.)"""

    maximum_block_size_exp = DEFAULT_BLOCK_SIZE_EXP
    """The maximum negotiated block size that can be sent to this remote."""

    maximum_payload_size = 1024
    """The maximum payload size that can be sent to this remote. Only relevant
    if maximum_block_size_exp is 7. This will be removed in favor of a maximum
    message size when the block handlers can get serialization length
    predictions from the remote. Must be divisible by 1024."""

    def as_response_address(self):
        """Address to be assigned to a response to messages that arrived with
        this message

        This can (and does, by default) return self, but gives the protocol the
        opportunity to react to create a modified copy to deal with variations
        from multicast.
        """
        return self

    @property
    def authenticated_claims(self):
        """Iterable of objects representing any claims (e.g. an identity, or
        generally objects that can be used to authorize particular accesses)
        that were authenticated for this remote.

        This is experimental and may be changed without notice.

        Its primary use is on the server side; there, a request handler (or
        resource decorator) can use the claims to decide whether the client is
        authorized for a particular request. Use on the client side is planned
        as a requirement on a request, although (especially on side-effect free
        non-confidential requests) it can also be used in response
        processing."""
        # "no claims" is a good default
        return ()

class MessageManager(metaclass=abc.ABCMeta):
    """The interface an entity that drives a MessageInterface provides towards
    the MessageInterface for callbacks and object acquisition."""

    @abc.abstractmethod
    def dispatch_message(self, message):
        """Callback to be invoked with an incoming message"""

    @abc.abstractmethod
    def dispatch_error(self, error: Exception, remote):
        """Callback to be invoked when the operating system indicated an error
        condition from a particular remote."""

    @property
    @abc.abstractmethod
    def client_credentials(self):
        """A CredentialsMap that transports should consult when trying to
        establish a security context"""

class TokenInterface(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def send_message(self, message, messageerror_monitor) -> Optional[Callable[[], None]]:
        """Send a message. If it returns a a callable, the caller is asked to
        call in case it no longer needs the message sent, and to dispose of if
        it doesn't intend to any more.

        messageerror_monitor is a function that will be called at most once by
        the token interface: When the underlying layer is indicating that this
        concrete message could not be processed. This is typically the case for
        RSTs on from the message layer, and used to cancel observations. Errors
        that are not likely to be specific to a message (like retransmission
        timeouts, or ICMP errors) are reported through dispatch_error instead.
        (While the information which concrete message triggered that might be
        available, it is not likely to be relevant).

        Currently, it is up to the TokenInterface to unset the no_response
        option in response messages, and to possibly not send them."""

    @abc.abstractmethod
    async def fill_or_recognize_remote(self, message):
        """Return True if the message is recognized to already have a .remote
        managedy by this TokenInterface, or return True and set a .remote on
        message if it should (by its unresolved remote or Uri-* options) be
        routed through this TokenInterface, or return False otherwise."""

class TokenManager(metaclass=abc.ABCMeta):
    # to be described in full; at least there is a dispatch_error in analogy to MessageManager's
    pass

class RequestInterface(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def fill_or_recognize_remote(self, message):
        pass

    @abc.abstractmethod
    def request(self, request: PlumbingRequest):
        pass

class RequestProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def request(self, request_message):
        """Create and act on a a :class:`Request` object that will be handled
        according to the provider's implementation.

        Note that the request is not necessarily sent on the wire immediately;
        it may (but, depend on the transport does not necessarily) rely on the
        response to be waited for."""

class Request(metaclass=abc.ABCMeta):
    """A CoAP request, initiated by sending a message. Typically, this is not
    instanciated directly, but generated by a :meth:`RequestProvider.request`
    method."""

    response = """A future that is present from the creation of the object and \
        fullfilled with the response message.

        When legitimate errors occur, this becomes an aiocoap.Error. (Eg. on
        any kind of network failure, encryption trouble, or protocol
        violations). Any other kind of exception raised from this is a bug in
        aiocoap, and should better stop the whole application.
        """

class Resource(metaclass=abc.ABCMeta):
    """Interface that is expected by a :class:`.protocol.Context` to be present
    on the serversite, which renders all requests to that context."""

    @abc.abstractmethod
    async def render(self, request):
        """Return a message that can be sent back to the requester.

        This does not need to set any low-level message options like remote,
        token or message type; it does however need to set a response code.

        A response returned may carry a no_response option (which is actually
        specified to apply to requests only); the underlying transports will
        decide based on that and its code whether to actually transmit the
        response."""

    @abc.abstractmethod
    async def needs_blockwise_assembly(self, request):
        """Indicator to the :class:`.protocol.Responder` about whether it
        should assemble request blocks to a single request and extract the
        requested blocks from a complete-resource answer (True), or whether
        the resource will do that by itself (False)."""

class ObservableResource(Resource, metaclass=abc.ABCMeta):
    """Interface the :class:`.protocol.ServerObservation` uses to negotiate
    whether an observation can be established based on a request.

    This adds only functionality for registering and unregistering observations;
    the notification contents will be retrieved from the resource using the
    regular :meth:`.render` method from crafted (fake) requests.
    """
    @abc.abstractmethod
    async def add_observation(self, request, serverobservation):
        """Before the incoming request is sent to :meth:`.render`, the
        :meth:`.add_observation` method is called. If the resource chooses to
        accept the observation, it has to call the
        `serverobservation.accept(cb)` with a callback that will be called when
        the observation ends. After accepting, the ObservableResource should
        call `serverobservation.trigger()` whenever it changes its state; the
        ServerObservation will then initiate notifications by having the
        request rendered again."""
